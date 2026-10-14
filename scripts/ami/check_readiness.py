"""Validate an operator-supplied AMI plan without calling AWS."""
import argparse
import json
from pathlib import Path
import re


def check(plan):
    outputs = plan.get("stack_outputs", {})
    template = plan.get("launch_template_data", {})
    tags = plan.get("launch_template_tags", {})
    network = plan.get("network", {})
    missing = []
    def require(value, message):
        if not value:missing.append(message)
    region = plan.get("region", "")
    require(isinstance(region,str) and re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d",region),"Supply the stack region")
    profile = outputs.get("TrainingInstanceProfileArn")
    require(isinstance(profile,str) and re.fullmatch(r"arn:aws(?:-cn|-us-gov)?:iam::\d{12}:instance-profile/.+",profile),"Supply TrainingInstanceProfileArn from stack outputs")
    require(bool(profile) and template.get("IamInstanceProfile") == {"Arn":profile},"Use the exact training profile ARN in IamInstanceProfile")
    require(bool(outputs.get("TrainingDocumentName")),"Supply TrainingDocumentName from stack outputs")
    require(bool(outputs.get("CheckpointsBucketName")),"Supply CheckpointsBucketName from stack outputs")
    require(isinstance(template.get("ImageId"),str) and re.fullmatch(r"ami-[a-f0-9]{8,17}",template["ImageId"]),"Supply the prepared AMI ID after authorized creation")
    require(bool(template.get("InstanceType")),"Supply an instance type")
    require(plan.get("image_architecture") in ("x86_64","arm64") and plan.get("image_architecture") == plan.get("instance_architecture"),"Declare matching image/instance architectures")
    require(not template.get("InstanceMarketOptions"),"Remove launch-template market overrides")
    require(tags.get("CostGuardManaged") == "true" and tags.get("CostGuardProtected", "false") != "true" and tags.get("Environment", "").lower() not in ("prod","production"),"Use opted-in, unprotected non-production template tags")
    require(plan.get("execution_enabled") is False,"Keep execution disabled during preparation")
    require(network.get("https_egress") is True,"Document outbound HTTPS access")
    if network.get("method") == "vpc_endpoints":
        for key in ("ssm_endpoint","ssmmessages_endpoint","s3_route","private_dns_enabled","endpoint_https_ingress"):
            require(network.get(key) is True,"Document network requirement: "+key)
    elif network.get("method") == "public_egress":
        require(network.get("dns_resolution") is True,"Document DNS resolution")
        require(network.get("ssm_s3_https_route") is True,"Document SSM/S3 HTTPS routing")
    else:require(False,"Select vpc_endpoints or public_egress network method")
    return {"plan_complete":not missing,"pending":missing,"live_verified":False,"aws_calls":0,
            "note":"Values are operator declarations; IAM, architecture, routes and SSM registration are not live-verified."}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("plan",type=Path)
    args=parser.parse_args()
    report=check(json.loads(args.plan.read_text()))
    print(json.dumps(report,indent=2))
    if not report["plan_complete"]:raise SystemExit(2)


if __name__=="__main__":main()
