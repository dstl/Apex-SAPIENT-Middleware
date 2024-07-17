#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import argparse
from distutils.file_util import copy_file
from itertools import chain
from pathlib import Path
from typing import Final

import pkg_resources
from grpc.tools import protoc

LATEST_VERSION: Final[Path] = Path(__file__).parent / "sapient_msg" / "bsi_flex_335_v2_0"


def generate(protos: list[str]):
    protoc_args = [
        "protoc",  # Dummy arg[0]
        "--python_out=.",
        "--pyi_out=.",
        "-I" + pkg_resources.resource_filename("grpc.tools", "_proto"),
        "-I.",
    ] + protos
    return protoc.main(protoc_args)


def main():
    protos = sorted(
        [str(p) for p in Path().rglob("sap*/**/*.proto")]
        + [str(p) for p in Path().rglob("tests/**/*.proto")]
    )
    print("Processing Proto files: \n" + "\n".join(protos))

    parser = argparse.ArgumentParser(description="Generate sapient protobuf to python bindings.")
    parser.add_argument(
        "files",
        metavar="FILES",
        type=str,
        nargs="*",
        help="Files against which to run. Defaults to all proto files in repo.",
        default=protos,
    )

    args = parser.parse_args()
    files = sorted(args.files)
    if ret := generate(files):
        print(f"Failed to generate proto files {ret}")
        exit(ret)

    copy_to_latest()


def copy_to_latest():
    for path in chain(LATEST_VERSION.glob("**/*_pb2.py"), LATEST_VERSION.glob("**/*_pb2.pyi")):
        out_path = (
            Path(__file__).parent / "sapient_msg" / "latest" / path.relative_to(LATEST_VERSION)
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        copy_file(str(path), str(out_path), update=True)


if __name__ == "__main__":
    main()
