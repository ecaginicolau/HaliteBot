from distutils.core import setup
from Cython.Build import cythonize

setup(
    name = "RampaBot",
    ext_modules = cythonize('bot/*.pyx'), requires=['PIL']
)