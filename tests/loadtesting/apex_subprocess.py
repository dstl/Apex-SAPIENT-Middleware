import json
from contextlib import contextmanager
from pathlib import Path
from subprocess import Popen
from tempfile import NamedTemporaryFile, TemporaryDirectory
from time import sleep
from typing import Mapping, Optional, Union

from sapient_apex_server.structures import SapientVersion
from sapient_msg.testing.messages import deepmerge, deepsplit


def apex_config(child_port: int = 5010, peer_port: int = 5001, **kwargs):
    template = {
        "logLevel": "INFO",
        "connections": [
            {
                "type": "Child",
                "port": child_port,
                "format": "PROTO",
                "icd_version": SapientVersion.LATEST.protocol_name,
            },
            {
                "type": "Peer",
                "port": peer_port,
                "format": "PROTO",
                "icd_version": SapientVersion.LATEST.protocol_name,
            },
        ],
        "elasticConfig": {
            "enabled": False,
        },
        "enableTimeSyncAdjustment": False,
        "messageMaxSizeKb": 1024,
        "detectionConfidenceFiltering": {
            "enable": False,
        },
        "middlewareId": "5913c0f4-9f89-4c01-ab90-939099797c4f",
        "enableMessageConversion": True,
        "autoAssignSensorIDInRegistration": {
            "enable": True,
            "startingID": 1000001,
        },
        "allowPeerRegistration": True,
        "sendRegistrationAck": True,
        "rollover": {"enable": False, "unit": "days", "value": 1},
        "validationOptions": {
            "validationTypes": [
                "mandatory_fields_present",
                "mandatory_oneof_present",
                "mandatory_repeated_present",
                "no_unknown_fields",
                "no_unknown_enum_values",
                "id_format_valid",
                "message_timestamp_reasonable",
                "detection_timestamp_reasonable",
                "supported_icd_version",
            ],
            "strictIdFormat": True,
            "messageTimestampRange": [-0.9, 0.1],
            "detectionMinimumGap": 0.08,
            "supportedIcdVersions": ["BSI Flex 335 v1.0", "BSI Flex 335 v2.0"],
        },
    }
    return deepmerge(template, deepsplit(**kwargs))


@contextmanager
def apex_subprocess(
    directory: Optional[Path] = None,
    configuration: Optional[Union[Mapping, Path]] = None,
    stdout: Optional[Path] = None,
    stderr: Optional[Path] = None,
    is_external: bool = False,
):
    if is_external:
        yield
        return

    temp_directory = TemporaryDirectory() or None
    if directory is None:
        dir = temp_directory.name
    else:
        dir = str(directory.absolute())

    temp_file = None
    if isinstance(configuration, Path) and not configuration.exists():
        raise ValueError(f"Configuration file {configuration} does not exist")
    elif isinstance(configuration, Path):
        config_path = str(configuration.absolute())
    else:
        temp_file = NamedTemporaryFile(dir=dir)
        temp_file.write(json.dumps(configuration or apex_config()).encode("utf-8"))
        temp_file.flush()
        config_path = temp_file.name

    stdout = stdout or (Path(dir) / "apex.out")
    stderr = stderr or (Path(dir) / "apex.err")

    process = None
    try:
        process = Popen(
            ["apex", config_path],
            stdout=stdout.open("w"),
            stderr=stderr.open("w"),
            cwd=dir,
        )
        while "Application startup complete" not in stderr.open("r").read():
            sleep(0.2)
        yield process
    finally:
        if process:
            process.terminate()
        if temp_file is not None:
            temp_file.close()
        if temp_directory is not None:
            temp_directory.cleanup()
