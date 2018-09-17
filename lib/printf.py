import datetime, sys

PURPLE = '\033[95m'
BLUE = '\033[94m'
GREEN = '\033[92m'
WARNING = '\033[93m'
RED = '\033[91m'
ENDC = '\033[0m'

def OK(count, msg):
	if count >= 0:
	    print GREEN + "[OK] " + msg + ENDC
		sys.stdout.flush()

def ERROR(count, msg):
    if count >= 0:
	    print RED + "[ERROR] " + msg + ENDC
		sys.stdout.flush()

def WARNING(count, msg):
    if count >= 1:
	    print WARNING + "[WARNING] " + msg + ENDC
		sys.stdout.flush()

def INFO(count, msg):
	if count >= 1:
		print BLUE + "[INFO] " + msg + ENDC
		sys.stdout.flush()

def DEBUG(count, msg):
	if count >= 3:
		print PURPLE + "[DEBUG]" + msg + ENDC
		sys.stdout.flush()