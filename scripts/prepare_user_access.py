"""Prepare a user-access DynamoDB item locally; no AWS calls."""
import argparse
from datetime import datetime, UTC
import json
from pathlib import Path
from boto3.dynamodb.types import TypeSerializer
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services.access_control import validate_grant


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--grant', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    grant = validate_grant(json.loads(args.grant.read_text()))
    item = {'subject': args.subject, 'grant': grant, 'is_active': not args.disable, 'updated_at': datetime.now(UTC).isoformat()}
    serializer = TypeSerializer()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output: json.dump({key: serializer.serialize(value) for key, value in item.items()}, output, indent=2)
    print(json.dumps({'item_file': str(args.output), 'active': item['is_active'], 'aws_calls': 0, 'applied': False}))


if __name__ == '__main__': main()
