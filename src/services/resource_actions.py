"""Conservative operation eligibility, independent of permission to execute."""


def supported_action(resource):
    properties = resource.properties or {}
    if resource.service == 'ec2':
        if (resource.state == 'running' and properties.get('root_device_type') == 'ebs'
                and not properties.get('lifecycle')):
            return 'stop'
    elif resource.service == 'rds':
        if (resource.state == 'available' and properties.get('engine') in {'mysql', 'mariadb', 'postgres'}
                and properties.get('multi_az') is False and properties.get('topology_observed') is True
                and not properties.get('cluster_id') and not properties.get('replica_source')
                and not properties.get('read_replicas')):
            return 'stop'
    elif resource.service == 'lambda':
        if resource.state == 'Active' and properties.get('function_name'):
            return 'limit_concurrency'
    return None
