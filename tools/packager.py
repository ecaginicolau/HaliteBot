#!/usr/bin/env python
import os
import zipfile
from datetime import datetime

def is_exclude(file):
    for ext in [".c","pyc",".pyd","exp","lib","obj",".log"]:
        if file.endswith(ext):
            return True
    return False

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            if not is_exclude(file):
                ziph.write(os.path.join(root, file))

if __name__ == '__main__':
    zipf = zipfile.ZipFile('submissions/MyBot_%s.zip' % datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), 'w', zipfile.ZIP_DEFLATED)
    zipdir('hlt', zipf)
    zipdir('bot', zipf)
    zipdir('log', zipf)
    zipf.write("MyBot.py")
    zipf.write("install.sh")
    zipf.write("configuration.pickle")
    zipf.write("configuration4.pickle")
    zipf.write("setup.py")
    zipf.close()