# coding=utf-8
# See main file for licence
# pylint: disable=W0702,R0201

"""
  Settings module.
"""
import os
import re

this_dir = os.path.dirname(os.path.abspath(__file__))

settings = {


    # name
    "name": u"builder v2.0",

    # logs
    "log_dir": os.path.join(this_dir, "..", "_logs"),

    "projects_top_dir": os.path.join(this_dir, "..", ".."),
    "builder": os.path.join(this_dir, "vcrun.bat"),

    "lines_to_show": 20,

    "configurations": {
        #"Debug-MT|Win32",
        "Debug-MT|x64",
        #"Release-MT|Win32",
        "Release-MT|x64",

        "Release|x64",
        "RelWithDebInfo|x64",

        #"Debug-MTDLL|Win32",
        #"Debug-MTDLL|x64",
        #"Release-MTDLL|Win32",
        #"Release-MTDLL|x64",
    },

    "project_defaults": {
        "solution_path": "projects",
        "solution": "*.sln",

        "output_libs": "libs",

        "copy": [
            "projects/output/*.lib",
            "projects/output/*.dll",
        ],
        "parallel": 2,
        "cleanup": (
            "projects/output/*.exe",
            "projects/output/*.lib",
            "projects/output/pdb/*.pdb",
            "libs/*.lib",
        ),
    },

    "projects": [
    ],
}
