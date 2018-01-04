import urllib.request, json
from pprint import pprint


def list_challenge(userid):
    url ="https://api.halite.io/v1/api/user/%s/challenge" % userid
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    #pprint(data)
    return data

def stat_challenge(userid, challenge):
    #Get adversary name:
    adversary = None
    for player, stat in challenge["players"].items():
        if player != userid:
            adversary=stat["username"]
    url = "https://api.halite.io/v1/api/user/%s/challenge/%s/match" % (userid, challenge["challenge_id"])
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    #pprint(data)
    wins = 0
    nb = 0
    for match in data:
        nb += 1
        for player, score in match["players"].items():
            #Me
            if player =="6389":
                if score["rank"]==1:
                    wins +=1
    print("[%s]Challenge against %s : Fought %s matches, won %s" % (challenge["time_created"],adversary, nb, wins))

if __name__ == "__main__":
    userid = 6389
    for challenge in list_challenge(userid):
        stat_challenge(userid, challenge)



