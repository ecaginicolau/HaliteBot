import multiprocessing
import ujson as json
import subprocess
import time
from pprint import pprint
import logging
import math
from bot.settings import config


class Consumer(multiprocessing.Process):

    def __init__(self, task_queue, result_queue, global_dic):
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
            # print('{}: {}'.format(proc_name, next_task))
            result = next_task()
            self.global_dic["nb"] += 1
            if result:
                self.global_dic["win"] += 1
            win = self.global_dic["win"]
            nb = self.global_dic["nb"]
            loop = self.global_dic["loop"]
            START_TIME = self.global_dic["START_TIME"]
            percent = (win / float(nb))
            current_time = time.time()
            avg_duration = (current_time - START_TIME) / float(nb)
            confidence_factor = 0.98 * 2  # 95%
            error_margin = math.sqrt((percent * (1 - percent)) / nb) * confidence_factor
            print("[Loop %s]Current score: %s/%s for %.2f%%, error margin: %.2f%%, avg duration: %.2f" % (loop, win, nb, percent * 100.0, error_margin * 100.0, avg_duration))
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
        # cmd = """halite.exe -r -q  -d "384 256" "python MyBot.py" "..\\HaliteBotV74\\run_bot.bat" "..\\HaliteBotV74\\run_bot.bat" "..\\HaliteBotV74\\run_bot.bat" """
        output = subprocess.check_output(cmd).decode("ascii")
        data = json.loads(output)
        # pprint( data)
        # return if a win
        win = data["stats"]["0"]["rank"] == 1
        # if win:
        #    print ("Game #%s is a %s" % (self.num, "win" if win else "loose"))
        return win

    def __str__(self):
        return 'Game #%s' % self.num


if __name__ == '__main__':
    logging.basicConfig(filename="mass_run.log", level=logging.DEBUG, filemode='w')

    # Establish communication queues
    tasks = multiprocessing.JoinableQueue()
    results = multiprocessing.Queue()
    mgr = multiprocessing.Manager()
    # Create a global dictionnary shared between processes
    global_dic = mgr.dict()

    # initialize some values
    global_dic["win"] = 0
    global_dic["nb"] = 0

    # Start consumers
    #num_consumers = int(multiprocessing.cpu_count() * 0.5)  # Don't overload the PC for this
    num_consumers = 6
    print("Creating %s consumers" % num_consumers)
    consumers = [Consumer(tasks, results, global_dic) for i in range(num_consumers)]

    nb_loop = 100
    # Start all consumers

    best_score = 0
    for w in consumers:
        w.start()


    """
    # Start of the configuration loop
    """
    for loop in range(nb_loop):
        # Time
        START_TIME = time.time()
        # initialize some values
        global_dic["loop"] = loop
        global_dic["win"] = 0
        global_dic["nb"] = 0
        global_dic["START_TIME"] = START_TIME
        # Enqueue jobs
        num_jobs = 500

        # Get the last best configuration
        config.load_configuration(filename="best_configuration.pickle", best=True)
        # Generate a new random step in the configuration
        config.random_step()
        # Save the configuration
        config.save_configuration(filename="configuration.pickle")

        logging.debug("New configuration test:")
        for key in sorted(config.handled_data.keys()):
            logging.debug("%s = %s" % (key, getattr(config, key)))

        # Create the tasks
        for i in range(num_jobs):
            id = i + (loop*num_jobs)
            tasks.put(Task(id))

        # Wait for all of the tasks to finish
        tasks.join()

        # Start printing results
        nb = 0
        nb_win = 0
        while num_jobs:
            result = results.get()
            nb += 1
            if result:
                nb_win += 1
            num_jobs -= 1

        percent = nb_win / float(nb)
        END_TIME = time.time()
        duration = END_TIME - START_TIME
        avg_duration = duration / nb
        confidence_factor = 0.98 * 2  # 95%
        error_margin = math.sqrt((percent * (1 - percent)) / nb) * confidence_factor
        print("[Best score: %.2f%%] Final stats: %s/%s wins, %.2f%%, error marin: %.2f%%, duration: %.2f, average duration: %.2f" % (best_score * 100.0, nb_win, nb, percent * 100.0, error_margin * 100.0, duration, avg_duration))
        logging.info("[Best score: %.2f%%] Final stats: %s/%s wins, %.2f%%, error marin: %.2f%%, duration: %.2f, average duration: %.2f" % (best_score * 100.0, nb_win, nb, percent * 100.0, error_margin * 100.0, duration, avg_duration))

        if percent > best_score:
            print("Best score!! %.2f%%" % (percent * 100.0))
            logging.debug("Best score!! %.2f%%" % (percent * 100.0))
            best_score = percent
            config.save_configuration(best=True)

    # We are done, terminate all consumers
    for consumer in consumers:
        consumer.terminate()
