import shutil

# copy all files from Scripts to .
shutil.copytree("Scripts", ".", dirs_exist_ok=True)

from getWebAPIs import *
from graphs import *
from helpFunctions import *
from mergeData import *
from pythongen import *
from templates import *
import argparse, logging



def generateAll(saveTo, logger):
    # mergeData.py -ga WEB_apis
    main_generateAPIs("Data", logger=logger)
    # mergeData.py -g Crawls/aggregated_both_modes_only.sqlite
    # pythongen.py --all_apis web-api-manager/sources/standard
    # pythongen.py --implemented_apis webextension/common/
    # getWebAPIs.py -aa all_apis.json -un unique_apis.json -F WEB_apis -a top_n_blocked.json -i implemented_apis.json
    # pythongen.py --common webextension/common --final final.json 


logger = setLogger("generateFinalLogs")

parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", help="Specify the output folder where json files will be stored")
args = parser.parse_args()
if args.all:
    print("Generating all files")
    generateAll(args.all, logger=logger)


# delete all *.py files from .
# for file in os.listdir("."):
#     if file.endswith(".py") and file != "generateFinal.py":
#         os.remove(file)