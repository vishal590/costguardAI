"""One explicit runtime counter; no pipeline-layer addition or billing inference."""
from datetime import datetime, timedelta, UTC
import math
from ..time_values import parse_utc_timestamp


def observe_counter(client, source, identity, start_date, end_date, *, variant=None, stage=None):
    if source not in ('lambda', 'sagemaker', 'bedrock', 'api_gateway_rest'):
        raise ValueError('Select one source: lambda, sagemaker, bedrock or api_gateway_rest')
    def text(value, label, maximum=2048):
        if not isinstance(value, str) or not value or len(value) > maximum or any(ord(character) < 32 for character in value):
            raise ValueError(f'Supply an explicit {label}')
        return value
    identity = text(identity, 'counter identity')
    start, end = start_date.date(), end_date.date()
    days = (end-start).days
    if not 1 <= days <= 31 or end > datetime.now(UTC).date(): raise ValueError('Use 1-31 completed daily dates with an exclusive end')
    start_time = datetime.combine(start, datetime.min.time(), UTC)
    end_time = datetime.combine(end, datetime.min.time(), UTC)
    if source == 'lambda':
        if ':' in identity: raise ValueError('Lambda source requires the unqualified FunctionName metric value')
        namespace, metric, statistic = 'AWS/Lambda', 'Invocations', 'Sum'
        dimensions = [{'Name': 'FunctionName', 'Value': identity}]
        semantics = 'function_invocations_including_function_errors_not_application_inferences'
    elif source == 'sagemaker':
        namespace, metric, statistic = 'AWS/SageMaker', 'Invocations', 'Sum'
        dimensions = [{'Name': 'EndpointName', 'Value': identity}, {'Name': 'VariantName', 'Value': text(variant, 'variant name', 128)}]
        semantics = 'selected_variant_invocations_not_a_verified_business_inference_count'
    elif source == 'bedrock':
        namespace, metric, statistic = 'AWS/Bedrock', 'Invocations', 'Sum'
        dimensions = [{'Name': 'ModelId', 'Value': identity}]
        semantics = 'successful_runtime_model_invocations_not_a_verified_business_inference_count'
    else:
        namespace, metric, statistic = 'AWS/ApiGateway', 'Count', 'SampleCount'
        dimensions = [{'Name': 'ApiName', 'Value': identity}, {'Name': 'Stage', 'Value': text(stage, 'REST API stage', 128)}]
        semantics = 'REST_API_stage_request_count_including_error_requests'
    expected = {int((start_time+timedelta(days=offset)).timestamp()) for offset in range(days)}
    points, failure = {}, None
    try:
        response = client.get_metric_statistics(Namespace=namespace, MetricName=metric, Dimensions=dimensions,
            StartTime=start_time, EndTime=end_time, Period=86400,
            Statistics=list(dict.fromkeys([statistic, 'SampleCount'])), Unit='Count')
        for point in response.get('Datapoints', []):
            stamp = int(parse_utc_timestamp(point['Timestamp']).timestamp())
            value, samples = float(point[statistic]), float(point['SampleCount'])
            if (stamp not in expected or not math.isfinite(value) or value < 0 or value > 2**53
                    or value != int(value) or not math.isfinite(samples) or samples <= 0): raise ValueError('Invalid counter observation')
            if stamp in points and points[stamp] != int(value): raise ValueError('Conflicting counter dates')
            points[stamp] = int(value)
        if sum(points.values()) > 2**53: raise ValueError('Counter precision is unavailable')
    except Exception:
        points, failure = {}, 'Counter observations could not be read or validated'
    complete = set(points) == expected
    return {'source': source, 'namespace': namespace, 'metric': metric, 'statistic': statistic,
        'dimensions': dimensions, 'region': getattr(getattr(client, 'meta', None), 'region_name', None),
        'status': 'available' if complete else 'partial' if points else 'unavailable',
        'total_count': sum(points.values()) if complete else None,
        'observed_subtotal': sum(points.values()) if points else None, 'complete_daily_coverage': complete,
        'daily': [{'date': datetime.fromtimestamp(stamp, UTC).date().isoformat(), 'count': points.get(stamp)} for stamp in sorted(expected)],
        'missing_dates': [datetime.fromtimestamp(stamp, UTC).date().isoformat() for stamp in sorted(expected-set(points))],
        'reason': failure, 'counter_semantics': semantics,
        'application_inference_count_verified': False, 'cost_attribution_verified': False}
