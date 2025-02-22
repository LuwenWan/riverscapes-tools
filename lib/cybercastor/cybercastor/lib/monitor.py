from termcolor import colored, cprint
from datetime import datetime
import json

possible_states = {'QUEUED': 'cyan', 'STARTING': 'cyan', 'RUNNING': 'yellow', 'STOPPED': 'red', 'SUCCEEDED': 'green', 'FAILED': 'red', 'DELETE_REQUESTED': 'red', 'STOP_REQUESTED': 'red'}
env_no_print = ['NO_UI']


def print_job(job):
    # Clear the screen and start printing our report

    program = "???"
    script = job['taskScriptId'] if 'taskScriptId' in job else '???'
    tags = ''
    try:
        if isinstance(job['env'], str) and len(job['env']) > 2:
            job['env'] = json.loads(job['env'])
        else:
            job['env'] = {}

        if 'PROGRAM' in job['env']:

            program = job['env']['PROGRAM']
            tags = colored(', '.join(['{}: {}'.format(k, v) for k, v in job['env'].items() if 'TAG' in k]), 'blue')
    except Exception as e:
        print(e)
        pass

    title = "{}  < {} / {} / {} >".format(job['name'], program, script, job['id'])

    cprint(title, 'white', attrs=['bold', 'underline'])

    # cprint('=' * title_length, 'magenta')

    if 'description' in job and len(job['description']) > 0:
        cprint('Description: {}'.format(job['description']), 'white')

    job_summary = {}
    print('{}'.format(tags))

    def print_status(status, color):
        queued_names = [t['name'] for t in job['tasks'] if t['status'] == status]
        job_summary[status] = len(queued_names)
        if (len(queued_names) > 0):
            cprint('\n{}: ({})'.format(status, len(queued_names)), color)
            cprint(', '.join(queued_names), color)

    [print_status(s, c) for s, c in possible_states.items()]
    print('')


def print_date(timestamp_ms_str):
    return datetime.utcfromtimestamp(int(timestamp_ms_str) / 1000).strftime('%b %d, %Y %H:%M:%S') + ' ({})'.format(timestamp_ms_str)


def report_job(job):
    output = ['']
    # Clear the screen and start printing our report
    output.append("{}  (id:{})".format(job['name'], job['id']))
    output.append('=================================================================')
    if 'description' in job and len(job['description']) > 0:
        output.append(job['description'])

    output.append('createdOn: {}'.format(print_date(job['createdOn'])))
    output.append('updatedOn: {}'.format(print_date(job['updatedOn'])))

    job_summary = {}

    def print_status(status, color):
        queuedNames = [t['name'] for t in job['tasks'] if t['status'] == status]
        job_summary[status] = len(queuedNames)
        if (len(queuedNames) > 0):
            output.append('\n{}: ({})'.format(status, len(queuedNames)))
            output.append(', '.join(queuedNames))

    [print_status(s, c) for s, c in possible_states.items()]

    output.append('\nJobs:')
    output.append('----------------')
    output.append('\t'.join(['jobname', 'taskname', 'status', 'cpu', 'memory', 'ellapsedS', 'startedOn', 'endedOn', 'logUrl', 'jobid', 'taskid']))
    for t in job['tasks']:
        if t['startedOn'] is None:
            ellapsed = 0
        elif t['endedOn'] is None:
            ellapsed = (int(t['queriedOn']) - int(t['startedOn'])) / 1000
        else:
            ellapsed = (int(t['endedOn']) - int(t['startedOn'])) / 1000

        output.append('\t'.join([job['name'], t['name'], t['status'], str(t['cpu']), str(t['memory']), str(ellapsed), str(t['startedOn']), str(t['endedOn']), str(t['logUrl']), job['id'], t['id']]))

    return '\n'.join(output)
