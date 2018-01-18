import multiprocessing
import ujson as json
import subprocess
import time
from pprint import pprint

import math

START_TIME = time.time()

class Consumer(multiprocessing.Process):

    def __init__(self, task_queue, result_queue,global_dic):
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.global_dic = global_dic


    def run(self):
        proc_name = self.name
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                # Poison pill means shutdown
                print('{}: Exiting'.format(proc_name))
                self.task_queue.task_done()
                break
            #print('{}: {}'.format(proc_name, next_task))
            result = next_task()
            self.global_dic["nb"] +=1
            if result:
                self.global_dic["win"] += 1
            win = self.global_dic["win"]
            nb = self.global_dic["nb"]
            percent = (win / float(nb))
            current_time = time.time()
            avg_duration = (current_time - START_TIME) / float(nb)
            confidence_factor = 0.98 *2 # 95%
            error_margin = math.sqrt((percent * (1 - percent)) / nb) * confidence_factor
            print("Current score: %s/%s for %.2f%%, error margin: %.2f%%, avg duration: %.2f" % (win, nb, percent * 100.0, error_margin * 100.0, avg_duration))
            self.task_queue.task_done()
            self.result_queue.put(result)


class Task:

    def __init__(self, num):
        self.num = num

    def __call__(self):
        """
        :param n: the number of the game, for log display
        :return:
        """
        # cmd = """halite.exe -r -q -d "240 160" "python MyBot.py" "..\\HaliteBotV74\\run_bot.bat" """
        cmd = """halite.exe -r -q -d "240 160" "python MyBot.py" "..\\HaliteHerve\\run_bot.bat" """
        #cmd = """halite.exe -r -q -d "312 206" "python MyBot.py" "..\\HaliteHerve\\run_bot.bat" """
        #cmd = """halite.exe -r -q  -d "384 256" "python MyBot.py" "..\\HaliteBotV59\\run_bot.bat" "..\\HaliteBotV59\\run_bot.bat" "..\\HaliteBotV59\\run_bot.bat" """
        # cmd = """halite.exe -r -q  -d "384 256" "python MyBot.py" "..\\HaliteHerve\\run_bot.bat" "..\\HaliteHerve\\run_bot.bat" "..\\HaliteHerve\\run_bot.bat" """
        output = subprocess.check_output(cmd).decode("ascii")
        data = json.loads(output)
        #pprint( data)
        # return if a win
        win = data["stats"]["0"]["rank"] == 1
        #if win:
        #    print ("Game #%s is a %s" % (self.num, "win" if win else "loose"))
        return win

    def __str__(self):
        return 'Game #%s' % self.num


if __name__ == '__main__':
    # Establish communication queues
    tasks = multiprocessing.JoinableQueue()
    results = multiprocessing.Queue()
    mgr = multiprocessing.Manager()
    #Create a global dictionnary shared between processes
    global_dic = mgr.dict()

    #initialize some values
    global_dic["win"] = 0
    global_dic["nb"] = 0

    # Start consumers
    num_consumers = int(multiprocessing.cpu_count() * 0.5) # Don't overload the PC for this
    print("Creating %s consumers" % num_consumers)
    consumers = [ Consumer(tasks, results, global_dic) for i in range(num_consumers)]

    for w in consumers:
        w.start()


    # Enqueue jobs
    num_jobs = 1000


    #time
    START_TIME=time.time()
    for i in range(num_jobs):
        tasks.put(Task(i))


    # Wait for all of the tasks to finish
    tasks.join()
    END_TIME = time.time()


    # Start printing results
    nb = 0
    nb_win = 0
    while num_jobs:
        result = results.get()
        nb +=1
        if result:
            nb_win +=1
        num_jobs -= 1

    percent = nb_win / float(nb)
    duration = END_TIME - START_TIME
    avg_duration = duration / nb

    confidence_factor = 0.98 *2 # 95%
    error_margin = math.sqrt((percent * (1 - percent)) / nb) * confidence_factor

    print("Final stats: %s/%s wins, %.2f%%, error marin: %.2f%%, duration: %.2f, average duration: %.2f" % (nb_win, nb, percent * 100.0, error_margin * 100.0, duration, avg_duration))

    for consumer in consumers:
        consumer.terminate()

