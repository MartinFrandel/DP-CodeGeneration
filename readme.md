
python pythongen.py --all_apis ../../web-api-manager/sources/standard
> generated all_apis.json


### getAPIS
> downloads all available apis from firefox page into WEB_apis folder
python .\mergeData.py -ga WEB_apis


### uniqe apis
> generate unique_apis.json , top_n_blocked.json
mergeData.py -g .\Crawls\aggregated_both_modes_only.sqlite

### get already implemented apis
python .\pythongen.py --implemented_apis ..\pagure\testing\webextension\common\
> genrate implemented_apis.json

### Merge apis
python .\getWebAPIs.py -aa APIS/all_apis.json -un APIS/unique_apis.json -F WEB_apis -a top_n_blocked.json -i APIS/implemented_apis.json
> generates final.json




python .\pythongen.py --common .\pagure\webextension\common\ --final .\APIS\final.json