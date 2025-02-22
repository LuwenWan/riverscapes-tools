'''Query Script to Find and delete projects on the server
    June 06, 2023
'''
from typing import Dict
import json
import os
import time
import requests
from cybercastor.classes.RiverscapesAPI import RiverscapesAPI
from rscommons import Logger
import inquirer


def string_same(label: str, local_obj: Dict[str, str], remote_obj: Dict[str, str]) -> bool:
    '''Compare two strings and return the difference

    Args:
        str1 (str): The first string
        str2 (str): The second string

    Returns:
        str: The difference between the two strings
    '''
    local = local_obj.get(label, '')
    remote = remote_obj.get(label, '')
    local = local.strip() if local is not None else ''
    remote = remote.strip() if remote is not None else ''
    if local != remote:
        print(f"  {label}")
        print(f"     REMOTE: \"{remote}\"")
        print(f"     LOCAL:  \"{local}\"")
        return False
    else:
        return True


def json_same(label: str, local_obj: Dict[str, any], remote_obj: Dict[str, any]) -> bool:
    '''Compare two json objects and return the difference

    Args:
        str1 (str): The first string
        str2 (str): The second string

    Returns:
        str: The difference between the two strings
    '''
    local = json.dumps(local_obj.get(label, []))
    remote = json.dumps(remote_obj.get(label, []))
    local = local.strip() if local is not None else ''
    remote = remote.strip() if remote is not None else ''
    if local != remote:
        print(f"  {label}")
        print(f"     REMOTE: \"{remote}\"")
        print(f"     LOCAL:  \"{local}\"")
        return False
    else:
        return True


def projectTypeSync(stage):
    ''' Find and delete projects on the server

    Args:
        stage (str): The stage to run the script on
    '''
    log = Logger(f"projectTypes::{stage}")
    log.title(f"Update Project types on stage: {stage}")

    # Create the API object. Note: this only works as a machine user
    riverscapes_api = RiverscapesAPI(stage=stage, machineAuth={
        'clientId': os.environ['RS_CLIENT_ID'],
        'secretId': os.environ['RS_CLIENT_SECRET'],
    })
    this_dir = os.path.dirname(__file__)

    def icon_file(machine_name):
        return os.path.join(this_dir, 'logos', f"{machine_name}.png")

    # Load the projectTypes.json file for comparison
    with open(os.path.join(this_dir, 'projectTypes.json'), 'r') as f:
        project_types_local = json.loads(f.read())

    # First get all the project types
    search_query = riverscapes_api.load_query('projectTypes')

    # Only refresh the token if we need to
    if riverscapes_api.accessToken is None:
        riverscapes_api.refresh_token()

    project_sort = {
        'same': [],
        'update': [],
        'create': [],
        'missing': [],
        'upload_logo': [],
        'delete_logo': [],
    }

    # Create a timedelta object with a difference of 1 day
    results = riverscapes_api.run_query(search_query, {})
    project_types_remote = results['data']['projectTypes']['items']

    # Now compare the two lists. the typical record looks like this:
    #       {
    #     'name': 'CAD Export',
    #     'summary': null,
    #     'description': null,
    #     'meta': [],
    #     'url': null,
    #     'machineName': 'CAD_Export',
    #     'state': 'ACTIVE',
    #     'logo': null
    #   },

    for pt_local in project_types_local:
        need_create = False
        remote_only = True
        for pt_remote in project_types_remote:
            if pt_local['machineName'] == pt_remote['machineName']:
                need_create = True
                # Compare the two records for these fields: name, summary, description, url, state, logo and meta
                # We do the meta compare by stringifying the json. It's crude but it works
                if not string_same('name', pt_local, pt_remote) \
                        or not string_same('summary', pt_local, pt_remote) \
                        or not string_same('description', pt_local, pt_remote) \
                        or not string_same('url', pt_local, pt_remote) \
                        or not string_same('state', pt_local, pt_remote) \
                        or not string_same('logo', pt_local, pt_remote) \
                        or not json_same('meta', pt_local, pt_remote):
                    print(f"Project type {pt_local['name']} needs updating")
                    project_sort['update'].append(pt_local)
                else:
                    project_sort['same'].append(pt_local)

                # Logos are a bit different. If it is remote but not local then we need to delete it. If it is local but not remote then we need to create it
                has_logo = os.path.isfile(icon_file(pt_local['machineName']))
                # We upload every logo. No harm in re-uploading
                if has_logo:
                    project_sort['upload_logo'].append(pt_local)

        # Now the reverse lookup to see if there are any remote only. We report these but don't delete them
        for pt_remote in project_types_remote:
            if pt_local['machineName'] != pt_remote['machineName']:
                remote_only = False
        if remote_only:
            project_sort['missing'].append(pt_local)
        if not need_create:
            project_sort['create'].append(pt_local)

    # Now we have to do the actions but first pause and confirm this is what we want to do
    print('The following actions will be performed:')
    if len(project_sort['same']) > 0:
        print(f"  {len(project_sort['same'])} project types are the same")
        print(f"      {', '.join([pt['machineName'] for pt in project_sort['same']])}")
        print('\n')
    if len(project_sort['create']) > 0:
        print(f"  {len(project_sort['create'])} project types will be created")
        print(f"      {', '.join([pt['machineName'] for pt in project_sort['create']])}")
        print('\n')
    if len(project_sort['update']) > 0:
        print(f"  {len(project_sort['update'])} project types will be updated")
        print(f"      {', '.join([pt['machineName'] for pt in project_sort['update']])}")
        print('\n')
    if len(project_sort['upload_logo']) > 0:
        print(f"  {len(project_sort['upload_logo'])} project type logos will be uploaded")
        print(f"      {', '.join([pt['machineName'] for pt in project_sort['upload_logo']])}")
        print('\n')
    if len(project_sort['delete_logo']) > 0:
        print(f"  {len(project_sort['delete_logo'])} project type logos will be deleted")
        print(f"      {', '.join([pt['machineName'] for pt in project_sort['delete_logo']])}")
        print('\n')
    if len(project_sort['missing']) > 0:
        print(f"  {len(project_sort['missing'])} project types ARE ON REMOTE BUT NOT LOCAL. NO OPERATION HERE.")
        print(f"      {', '.join([pt['machineName'] for pt in project_sort['missing']])}")
        print('\n')
    questions = [
        inquirer.Confirm('continue', message=f"This will change [[{stage.upper()}]]. Do you want to continue?")
    ]
    answers = inquirer.prompt(questions)
    if not answers['continue']:
        print('Exiting')
        exit()

    # First create the missing project types
    create_mutation = riverscapes_api.load_mutation('createProjectType')
    for pt in project_sort['create']:
        print(f"Creating project type: {pt['name']}")
        response = riverscapes_api.run_query(create_mutation, {
            'id': pt['machineName'],
            'projectType': {
                'name': pt['name'],
                'summary': pt['summary'],
                'description': pt['description'],
                'url': pt['url'],
                'meta': pt['meta'],
            },
            'state': pt['state']
        })
        pass

    # Now update the project types that need updating
    update_mutation = riverscapes_api.load_mutation('updateProjectType')
    for pt in project_sort['update']:
        print(f"Updating project type: {pt['name']}")
        riverscapes_api.run_query(update_mutation, {
            'id': pt['machineName'],
            'projectType': {
                'name': pt['name'],
                'summary': pt['summary'],
                'description': pt['description'],
                'url': pt['url'],
                'meta': pt['meta'],
            },
            'state': pt['state']
        })

    # Now delete the logos that need to be deleted
    for pt in project_sort['delete_logo']:
        print(f"Updating project type: {pt['name']}")
        riverscapes_api.run_query(update_mutation, {'projectType': {'clearLogo': True}})

    # Now upload the logos that need to be uploaded
    request_upload_image = riverscapes_api.load_query('requestUploadImage')
    check_upload = riverscapes_api.load_query('checkUpload')
    print('Uploading logos')
    for pt in project_sort['upload_logo']:
        print(f"  Uploading logo for project type: {pt['name']}")
        print(f"      Requesting upload for project type logo: {pt['name']}")
        upload_request = riverscapes_api.run_query(request_upload_image, {'entityId': pt['machineName'], 'entityType': 'PROJECT_TYPE'})
        token = upload_request['data']['requestUploadImage']['token']
        upload_url = upload_request['data']['requestUploadImage']['url']
        upload_fields = upload_request['data']['requestUploadImage']['fields']

        print(f"      Uploading logo for project type: {pt['name']}")
        # Now we need to upload to S3 using the fields and url
        upload_result = requests.post(upload_url, data=upload_fields, files={'file': open(icon_file(pt['machineName']), 'rb')})
        if not upload_result.ok:
            print(f"      Upload failed: {upload_result.status_code}")
            print(upload_result.text)
            continue

        # Now check the upload status up to 5 times at 5 seconds each
        print('      Waiting for upload to complete')
        retries = 0
        while True and retries < 5:
            check_query = riverscapes_api.run_query(check_upload, {'token': token})
            if check_query['data']['checkUpload']['status'] == 'SUCCESS':
                break
            elif retries > 5:
                print('      Upload failed')
                break
            else:
                retries += 1
                print('      Waiting for upload to complete')
                time.sleep(5)

        print(f"  Updating project type: {pt['name']}")
        riverscapes_api.run_query(update_mutation, {
            'id': pt['machineName'],
            'projectType': {
                'logoToken': token
            }
        })

    # Shut down the API since we don;t need it anymore
    riverscapes_api.shutdown()

    log.info('Done!')


if __name__ == '__main__':
    projectTypeSync('staging')
    projectTypeSync('production')
