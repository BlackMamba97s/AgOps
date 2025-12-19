import json
import argparse
import re


def split_version(version):
    if args.prefix:
        version = version.replace(args.prefix, '')
    tmp = version.split('-')
    build = int(tmp[1]) if len(tmp) == 2 else 0
    tmp = tmp[0].split('.')
    return (int(tmp[0]), int(tmp[1]), int(tmp[2]), build)


def check_max(versions, sprint=None):
    found = False
    max_v = [0, 1, 0, 0]
    if sprint:
        max_v[0] = int(sprint)
    for version in versions:
        if version == 'latest':
            continue
        major, minor, fix, build = split_version(version)
        if sprint and int(sprint) != major:
            continue
        if major < max_v[0] or (major == max_v[0] and minor < max_v[1]) or (major == max_v[0] and minor == max_v[1] and fix < max_v[2]) or (major == max_v[0] and minor == max_v[1] and fix == max_v[2] and build < max_v[3]):
            continue
        max_v = [major, minor, fix, build]
        found = True
    return (max_v, found)


def old_version(versions, u_type):
    old_version, found = check_max(versions, args.sprint)
    v = '{}{}.{}.{}'.format(prefix, old_version[0], old_version[1], old_version[2])
    return v


def prepare_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--versions', '-v', required=True,
                        help='Versions in a json file, list format is required')
    parser.add_argument('--version-key', help='')
    parser.add_argument('--type', '-t', required=True,
                        choices=['sprint', 'minor', 'fix'], help='Type of upgrade')
    parser.add_argument('--prefix', '-p', help='')
    parser.add_argument(
        '--sprint', help='Force the script to use the passed sprint number')
    return parser.parse_args()


args = prepare_args()

prefix = args.prefix if args.prefix else ""
tags = None
with open(args.versions, 'r') as f:
    tags = json.load(f)

versions = tags[args.version_key]

print((old_version(versions, args.type)))