import datetime

PURPLE = '\033[95m'
BLUE = '\033[94m'
GREEN = '\033[92m'
WARNING = '\033[93m'
RED = '\033[91m'
ENDC = '\033[0m'

def OK(msg):
    print GREEN + "[OK] " + msg + ENDC

def ERROR(msg):
    print RED + "[ERROR] " + msg + ENDC

def WARNING(msg):
    print WARNING + "[WARNING] " + msg + ENDC

def INFO(msg):
    print BLUE + "[INFO] " + msg + ENDC

def DEBUG(msg):
	print PURPLE + "[DEBUG]" + msg + ENDC