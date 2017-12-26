#!/usr/bin/env python
import os
import zipfile
from datetime import datetime
def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))

if __name__ == '__main__':
    zipf = zipfile.ZipFile('submissions/%s_MyBot.zip' % datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), 'w', zipfile.ZIP_DEFLATED)
    zipdir('hlt', zipf)
    zipf.write("MyBot.py")
    zipf.write("monitor.py")
    zipf.write("manager.py")
    zipf.write("drone.py")
    zipf.close()