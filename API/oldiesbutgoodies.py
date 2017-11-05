#!/usr/bin/env python3

import API.athenahealth.athenahealthapi as athenahealthapi
import datetime
import pandas as pd

####################################################################################################
# Setup
####################################################################################################
key = '5zthy7bfyqn8krrk4n2ghnqz'
secret = 'RYa479xrVEJ5ceQ'
version = 'preview1'
practiceid = 000000

api = athenahealthapi.APIConnection(version, key, secret, practiceid)

# If you want to change which practice you're working with after initialization, this is how.
api.practiceid = 195900


# here's a useful function for construct the URL
def path_join(*args):
    return ''.join('/' + str(arg).strip('/') for arg in args if arg)


####################################################################################################
# GET departments

def get_department_id_list():
    departments = api.GET('/departments', {
        "showalldepartments": "true"
    })
    return departments['departments']
