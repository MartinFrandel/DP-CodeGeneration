from getWebAPIs import *
from graphs import *
from helpFunctions import *
from mergeData import *
from pythongen import *
from templates import *
import json
import logging

logger = setLogger("generateFinalLogs")

# mergeData.py -g aggregated_both_modes_only.sqlite
# main_graphs(filepath="aggregated_both_modes_only.sqlite", logger=logger)

# # pythongen.py --all_apis web-api-manager/sources/standards
# apis = all_apis("web-api-manager/sources/standards")
# with open(f"all_apis.json", "w") as f:
#             json.dump(apis, f, indent=4)

# # pythongen.py --implemented_apis webextension/common/
# implemented_apis("webextension/common/")

# # getWebAPIs.py -aa all_apis.json -un unique_apis.json -F WEB_apis -a top_n_blocked.json -i implemented_apis.json
# combineSources("all_apis.json", "unique_apis.json", "WEB_apis", "top_n_blocked.json", "implemented_apis.json")

# pythongen.py --common webextension/common --final final.json
generate_common("webextension/common", "final.json", None)