"""MODULE TO INTERACT WITH POLLINATION CLOUD
UPLOADS, WAITS FOR PROCESSING AND DOWNLOADS RESULTS"""

import pathlib
import requests
import time
import zipfile
import tempfile
import shutil
import re
import json
from urllib.error import HTTPError

from pollination_streamlit.api.client import ApiClient
from pollination_streamlit.interactors import NewJob, Recipe, Job
from queenbee.job.job import JobStatusEnum

#####
# UPLOAD THE STUDIES
#####
# Study name: Any name for the simulation
# Api client: Pollination cloud client with token
# owner: the username in pollination cloud
# project: Name of the project folder for user in the cloud
# epw: local path to the epw file
# ddy: local path to the local ddy file
# models_folder: local folder to the hbjson models
def submit_study(
    study_name: str, api_client: ApiClient, owner: str, project: str, epw: pathlib.Path,
        ddy: pathlib.Path, sim_pars: pathlib.Path, models_folder: pathlib.Path) -> Job:

    print(f'Creating a new study: {study_name}')
    # Assumption: the recipe has been already added to the project
    recipe = Recipe('ladybug-tools', 'annual-energy-use', '0.5.3', client=api_client)

    input_folder = pathlib.Path(models_folder)

    # create a new study
    new_study = NewJob(owner, project, recipe, client=api_client)
    new_study.name = study_name
    new_study.description = f'Annual Energy Simulation {input_folder.name}'

    # upload the weather files - you only need to upload them once, and you can use
    # the path to them directly
    assert epw.is_file(), f'{epw} is not a valid file path.'
    assert ddy.is_file(), f'{ddy} is not a valid file path.'
    assert sim_pars.is_file(), f'{sim_pars} is not a valid file path.'

    epw_path = new_study.upload_artifact(epw, target_folder='weather-data')
    ddy_path = new_study.upload_artifact(ddy, target_folder='weather-data')
    pars_path = new_study.upload_artifact(sim_pars, target_folder='sim-par')

    recipe_inputs = {
        'epw': epw_path,
        'ddy': ddy_path,
        'sim-par': pars_path
    }
    
    # Iterates in the given folder and uploads all the hbjson it finds!
    study_inputs = []
    for model in input_folder.glob('*.hbjson'):
        inputs = dict(recipe_inputs)  # create a copy of the recipe
        # upload this model to the project
        print(f'Uploading model: {model.name}')
        uploaded_path = new_study.upload_artifact(model, target_folder=input_folder.name)
        inputs['model'] = uploaded_path
        inputs['model_id'] = model.stem  # use model name as the ID.
        study_inputs.append(inputs)

    # add the inputs to the study
    # each set of inputs create a new run
    new_study.arguments = study_inputs

    # # create the study
    running_study = new_study.create()

    job_url = f'https://app.pollination.cloud/{running_study.owner}/projects/{running_study.project}/jobs/{running_study.id}'
    print(job_url)
    time.sleep(5)
    return running_study

#####
# UPLOAD ONLY THE MODELS (avoid re-uploading common files)
#####
def upload_models(epw_cld, ddy_cld, sim_par_cld, model_upfld, std):    
    #Send all the geometries in the upload file to the cloud   
    recipe_inputs = {
        'epw': epw_cld,
        'ddy': ddy_cld,
        'sim-par': sim_par_cld
    }
    
    #Iterates in the given folder and uploads all the hbjson it finds
    study_inputs = [] # Has the name and id of each model
    for model in model_upfld.glob('*.hbjson'): # THIS UPLOADS ALL HBJSONS FROM ALL GENS!
        inputs = dict(recipe_inputs)  # create a copy of the recipe
        #upload this model to the project
        print(f'Uploading model: {model.name}')
        uploaded_path = std.upload_artifact(model, target_folder=model_upfld.name)
        inputs['model'] = uploaded_path
        inputs['model_id'] = model.stem  # use model name as the ID.
        study_inputs.append(inputs)
    
    #add the inputs to the study
    #each set of inputs create a new run
    std.arguments = study_inputs
    
    # create the study
    running_study = std.create()
    
    job_url = f'https://app.pollination.cloud/{running_study.owner}/projects/{running_study.project}/jobs/{running_study.id}'
    print(job_url)
    time.sleep(5)

    return running_study

#####
# CHECK THE STATUS OF THE STUDY
#####
# Study is the current job
def check_study_status(study: Job):
    """"""
    status = study.status.status

    while True:
        status_info = study.status
        http_errors = 0
        print('\t# ------------------ #')
        print(f'\t# pending runs: {status_info.runs_pending}')
        print(f'\t# running runs: {status_info.runs_running}')
        print(f'\t# failed runs: {status_info.runs_failed}')
        print(f'\t# completed runs: {status_info.runs_completed}')
        if status in [
            JobStatusEnum.pre_processing, JobStatusEnum.running, JobStatusEnum.created,
            JobStatusEnum.unknown
        ]:
            time.sleep(15)            
            try:
                study.refresh()
            except HTTPError as e:
                status_code = e.response.status_code
                print(str(e))
                if status_code == 500:
                    http_errors += 1
                    if http_errors > 5:
                        # failed for than 3 times with no success
                        raise HTTPError(e)
                    # wait for additional 15 seconds
                    time.sleep(15)
            else:
                http_errors = 0
                status = status_info.status
            
    #         study.refresh()
    #         status = status_info.status
        else:
            # study is finished
            time.sleep(2)
            break
        

#####
# DOWNLOAD THE RESULTS
#####
# owner: attribute from study object
# project: attribute from study object
# study_id: attribute from study object
# download_folder: local path to the folder where the results will be downloaded
# api_client: Pollination client with token (preset value 1)
# page: Initial page of the folder from where data will be downloaded (preset value 1)
def _download_results(
    owner: str, project: str, study_id: int, download_folder: pathlib.Path,
    api_client: ApiClient, page: int = 1
        ):
    print(f'Downloading page {page}')
    per_page = 25
    url = f'https://api.pollination.cloud/projects/{owner}/{project}/runs'
    params = {
        'job_id': study_id,
        'status': 'Succeeded',
        'page': page,
        'per-page': per_page
    }
    response = requests.get(url, params=params, headers=api_client.headers)
    response_dict = response.json()
    runs = response_dict['resources']
    temp_dir = tempfile.TemporaryDirectory()
    # with tempfile.TemporaryDirectory() as temp_dir:
    if temp_dir:
        temp_folder = pathlib.Path(temp_dir.name)
        for run in runs:
            run_id = run['id']
            # the model-id is hardcoded in submit_study. This is not necessarily good
            # practice and makes the code to only be useful for this example.
            input_id = [
                inp['value']
                for inp in run['status']['inputs'] if inp['name'] == 'model_id'
            ][0]
            run_folder = temp_folder.joinpath(input_id)
            eui_file = run_folder.joinpath('eui.json')
            out_file = download_folder.joinpath(f'{input_id}.json')
            print(f'downloading {input_id}.json to {out_file.as_posix()}')
            run_folder.mkdir(parents=True, exist_ok=True)
            download_folder.mkdir(parents=True, exist_ok=True)
            url = f'https://api.pollination.cloud/projects/{owner}/{project}/runs/{run_id}/outputs/eui'
            signed_url = requests.get(url, headers=api_client.headers)
            output = api_client.download_artifact(signed_url=signed_url.json())
            with zipfile.ZipFile(output) as zip_folder:
                zip_folder.extractall(run_folder.as_posix())
            # move the json file to study folder
            shutil.copy(eui_file.as_posix(), out_file.as_posix())

    next_page = response_dict.get('next_page')
    if next_page is not None:
        time.sleep(1)
        _download_results(
            owner, project, study_id, download_folder, api_client, page=next_page
        )

# ASSIGN THE VARIABLES DEPENDING OF OBJECT ATTRIBUTES TO PREVIOUS FUNCTION
def download_study_results(
        api_client: ApiClient, study: Job, output_folder: pathlib.Path):
    owner = study.owner
    project = study.project
    study_id = study.id

    _download_results(
        owner=owner, project=project, study_id=study_id, download_folder=output_folder,
        api_client=api_client
    )
    
#####
# READ DOWNLOADED JSONS
#####
# preset data needed is total energy, if false is EUI
def read_jsons(down_fold, data_needed = True):
    pattern  = ".*" + "-"
    curr_dta = {}
    for outpt in down_fold.glob('*.json'):
        # Get rid of the extension
        f_name = outpt.stem
        
        # delete everything before pattern (-)
        ag_num = re.sub(pattern, '', f_name)
        
        # Open JSON file for the current agent
        f = open(outpt)
      
        # return JSON object as a dictionary
        data = json.load(f)
      
        # Get needed data from JSON
        if data_needed:
            toteg_ag = data['total_energy']
        else:
            toteg_ag = data['eui']        
        
        # Closing file
        f.close()
        
        # THIS WORKS FOR THE BLOCK CLASS
        #curr_dta[int(ag_num)] = toteg_ag
        
        # On the neigh class this is replaced by
        curr_dta[ag_num] = toteg_ag
        
    return curr_dta