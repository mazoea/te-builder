# coding=utf-8
# See main file for licence
# pylint: disable=W0702,R0201,C0111,W0613,R0914,W0612,R0913,R0902

"""
    Own language detection
"""
import glob
import os
import sys
import re
from time import time as time_fnc
import time
import json
import shutil
from settings import settings
import logging
import getopt
import tempfile
import subprocess
import locale
import codecs
from time import sleep

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
_logger = logging.getLogger()


# ======================================================
# back ported
# ======================================================

# noinspection PyBroadException
def uni(str_str, encoding="utf-8"):
    """ Try to get unicode without errors """
    try:
        if isinstance(str_str, unicode):
            return str_str
        elif isinstance(str_str, basestring):
            return unicode(str_str, encoding)
    except UnicodeError:
        pass
    try:
        return unicode(str(str_str),
                       encoding=encoding,
                       errors='ignore')
    except UnicodeError:
        pass
    try:
        return str_str.decode(encoding=encoding,
                              errors="ignore")
    except Exception:
        pass
    _logger.critical(
        "Could not convert [something] to unicode")
    return u""


def exists_key(special_format_key_str, dict_inst, return_val=False):
    """ Checks whether a recursive key exists defined in dot format."""
    parts = special_format_key_str.split(".")
    d = dict_inst
    for part in parts:
        if part is None or part not in d:
            return (False, None) if return_val else False
        d = d[part]
    return (True, d) if return_val else True


# noinspection PyBroadException
def safe_unlink(file_path):
    """
        Safe delete of a file looping up to 1 sec.

        .. note::

          On some systems (i.e., Windows) the process can still `somehow` have the file opened.
    """
    assert isinstance(file_path, basestring)
    max_loops = 10
    while 0 < max_loops:
        try:
            os.unlink(file_path)
            return
        except Exception as e:
            sleep(0.1)
            if max_loops == 1:
                _logger.warning("Could not remove file [%s] [%s]",
                                file_path,
                                repr(e))
        finally:
            max_loops -= 1


DEBUG_DRY_RUN = 1


def run(env_dict, cmd, logger=None, debug=0, cwd=None):
    """
        Run local process using command line in cmd.

        Returns

          return code
          stdout
          stderr
          took time
    """
    took = 0.
    if DEBUG_DRY_RUN < debug:
        _logger.warning("Running in debug mode => not executing (%s)", cmd)
        return 0, "", "", took

    start = time_fnc()
    temp_dir = env_dict.get("temporary_directory", "") or None

    tempik_stdout = tempfile.NamedTemporaryFile(
        mode="w+b",
        suffix=".cmd.stdout.txt",
        dir=temp_dir,
        delete=False
    )
    tempik_stderr = tempfile.NamedTemporaryFile(
        mode="w+b",
        suffix=".cmd.stderr.txt",
        dir=temp_dir,
        delete=False
    )
    if logger:
        logger.debug(u"Running [%s] into\n  [%s]\n  [%s]",
                     uni(cmd),
                     tempik_stdout.name,
                     tempik_stderr.name)
    try:
        cmd = cmd.encode(locale.getpreferredencoding())
    except:
        pass
    p = subprocess.Popen(
        cmd,
        shell=True,
        stdin=None,
        stdout=tempik_stdout,
        stderr=tempik_stderr,
        cwd=cwd,
    )

    # wait for the end
    p.communicate()

    tempik_stdout.close()
    tempik_stderr.close()

    took = round(time_fnc() - start, 2)
    ret = [None, None]
    try:
        with codecs.open(tempik_stdout.name, "r", "utf-8", errors='replace') as ftemp:
            ret[0] = ftemp.read().strip()
        with codecs.open(tempik_stderr.name, "r", "utf-8", errors='replace') as ftemp:
            ret[1] = ftemp.read().strip() or None
    except Exception as e:
        _logger.warning("Run problem with [%s][%s][%s]", cmd, ret[0], str(e))

    if not exists_key("runners.cleanup", env_dict) or env_dict["runners"]["cleanup"]:
        safe_unlink(tempik_stdout.name)
        safe_unlink(tempik_stderr.name)

    return p.returncode, ret[0], ret[1], took


def extend_dict(what, with_what):
    """ Extend dicts instead of replace items.  """
    for k, v in with_what.iteritems():
        if k in what and isinstance(what[k], dict):
            extend_dict(what[k], v)
        else:
            what[k] = v


def get_bs(env, build_dict, key):
    if key not in build_dict:
        assert key in env["project_defaults"]
        return env["project_defaults"][key]
    else:
        return build_dict[key]


# ======================================================
# build run
# ======================================================

def validate_configuration(sln_file, configuration):
    magic = "SolutionConfigurationPlatforms"
    non_magic = "EndGlobalSection"
    available_configurations = []
    start = False
    for l in open(sln_file, mode="r").readlines():
        if magic in l:
            start = True
            continue
        if start and non_magic in l:
            break
        if start:
            available_configurations.append(l.split("=")[1].strip())
    return configuration in available_configurations


def cmake_batch(env, project_dir, build_dict):
    """
        Return cmake batch file if present
    """
    cmaker = os.path.join(
        project_dir, get_bs(env, build_dict, "cmake_batch"))
    return cmaker if os.path.exists(cmaker) else None


def msvc_solution(env, project_dir, build_dict):
    """
        Is an MSVC solution already present?
    """
    project_sln_dir = os.path.join(
        project_dir, get_bs(env, build_dict, "solution_path"))
    sln_files = glob.glob(
        os.path.join(project_sln_dir, get_bs(env, build_dict, "solution"))
    )
    if len(sln_files) > 1:
        sln_files = [x for x in sln_files if x.endswith("project.sln")]

    return sln_files[0] if 1 == len(sln_files) else None


def cmaker_build_run(env, project_name, cmaker):

    def _build():
        to_show = lines_to_show
        cmd = cmaker + " nopause"
        _logger.info("Executing \n%s", "\n\t".join(cmd.split()))
        ret, stdout, stderr, took = run({}, cmd, _logger, cwd=os.path.dirname(cmaker))
        if 0 != ret:
            to_show *= 10
        _logger.info("Took [%s], ret code [%d]", took, ret)
        stdout_lines = stdout.splitlines()
        _logger.info("\n\n" + 20 * "-")
        _logger.info("\n".join(stdout_lines[-to_show:]))
        if len(stderr or "") > 0:
            _logger.critical(stderr)
        p = re.compile(r"(\d+) Error\(s\)")
        for line in stdout_lines[-to_show:]:
            m = p.search(line)
            if m:
                if 0 < int(m.group(1)):
                    return ret, line + 10 * "!"
                else:
                    return ret, line
        return ret, None

    ret, ret_line = _build()
    _logger.info(20 * "-" + "\n\n")
    return ret, "%15s : CMAKER : %15s" % (project_name, ret_line)


def msvc_build_run(env, project_name, sln_file, configuration, build_dict, parallel=1, lines_to_show=15):
    """
        msvc:
            ```vcrun.bat g:\textextractor\projects\te-external\zlib\projects\project.vc2010.sln /Rebuild "Debug-MT|Win32" /OUT "DEBUG-MT.log"```

    """
    conf, platform = configuration.split("|")
    msvcbuilder = env["msvc-builder"]

    def _build(command="rebuild"):
        to_show = lines_to_show
        cmd = "%s \"%s\" /t:%s \"/p:configuration=%s,platform=%s\" /m:%s \"/fileLoggerParameters:LogFile=%s\" /nologo" % (
            msvcbuilder, sln_file, command, conf, platform, parallel, logfile
        )
        _logger.info("Executing \n%s", "\n\t".join(cmd.split()))
        ret, stdout, stderr, took = run({}, cmd, _logger)
        if 0 != ret:
            to_show *= 10
        _logger.info("Took [%s], ret code [%d]", took, ret)
        stdout_lines = stdout.splitlines()
        _logger.info("\n\n" + 20 * "-")
        _logger.info("\n".join(stdout_lines[-to_show:]))
        if len(stderr or "") > 0:
            _logger.critical(stderr)
        p = re.compile(r"(\d+) Error\(s\)")
        for line in stdout_lines[-to_show:]:
            m = p.search(line)
            if m:
                if 0 < int(m.group(1)):
                    return ret, line + 10 * "!"
                else:
                    return ret, line
        return ret, None

    # find out available configurations
    ok = validate_configuration(sln_file, configuration)
    if not ok:
        return 0, "%15s : %20s : %15s" % (project_name, configuration, "CONFIGURATION NOT FOUND")

    log_file_name = "%s.%s.log" % (
        project_name, configuration.replace("|", "-"))
    logfile = os.path.join(env["log_dir"], log_file_name)

    ret, ret_line = _build()
    for i in range(build_dict.get("try", 0)):
        ret1, ret_line = _build("build")
        ret += ret1

    _logger.info(20 * "-" + "\n\n")
    return ret, "%15s : %20s : %15s" % (project_name, configuration, ret_line)


# ======================================================
# cleanup
# ======================================================

def cleanup_libs(env, project_dir, build_dict):
    """
        Delete libs
    """
    for copy_glob in get_bs(env, build_dict, "cleanup"):
        copy_glob = os.path.join(project_dir, copy_glob)
        for f in glob.glob(copy_glob):
            try:
                _logger.info("Deleting [%s]", f)
                os.remove(f)
            except Exception as e:
                _logger.critical(
                    "Could not remove [%s] because of [%s]", f, repr(e))


def copy_libs(env, project_dir, build_dict):
    """
        Delete libs
    """
    for cl in get_bs(env, build_dict, "copy"):
        copy_glob = os.path.join(project_dir, cl)
        output_lib_dir = os.path.join(
            project_dir, get_bs(env, build_dict, "output_libs")
        )
        try:
            os.makedirs(output_lib_dir)
        except:
            pass
        for file_created in glob.glob(copy_glob):
            _logger.info("Copying [%s] to [%s]", file_created, output_lib_dir)
            shutil.copy(file_created, output_lib_dir)


# ======================================================
#
# ======================================================

def foreach(env):
    # for all configurations execute run
    changed = True
    for configuration in env["configurations"]:
        for build_dict in env["projects"]:
            project_dir = os.path.join(
                env["projects_top_dir"], build_dict["path"])
            yield configuration, build_dict, project_dir, changed
            changed = False
        changed = True


def parse_command_line(env):
    """ Parses the command line arguments. """
    opts = None
    try:
        options = [
            "settings=",
        ]
        input_options = sys.argv[1:]
        opts, _ = getopt.getopt(input_options, "", options)
    except getopt.GetoptError as e:
        _logger.info(u"Invalid arguments [%s]", e)
        sys.exit(1)

    found= False
    for option, param in opts:
        if option == "--settings":
            found = True
            _logger.info("Using [%s] settings", param)
            if os.path.exists(param):
                input_settings = json.load(
                    open(param, mode="r"), encoding="utf-8")
                extend_dict(env, input_settings)
            else:
                k, v = param.split("=")
                env[k] = v
            continue
    return env, found


if __name__ == "__main__":
    s = time.time()
    try:
        os.makedirs(settings["log_dir"])
    except:
        pass

    env, found = parse_command_line(settings)
    if not found:
        available_settings = glob.glob("*.json")
        _logger.info("\n" + "\n".join(
            ["%2d. %s" % (i, x) for i, x in enumerate(available_settings)])
        )
        idx = raw_input("Select configuration> ")
        build_settings = available_settings[int(idx)]
        build_settings = json.load(
            open(build_settings, mode="r"), encoding="utf-8")
        extend_dict(env, build_settings)

    # for all configurations execute run
    for configuration, build_dict, project_dir, _1 in foreach(env):
        cleanup_libs(env, project_dir, build_dict)

    # for all configurations execute run
    s = time.time()
    build_status = []
    ret = 0
    for configuration, build_dict, project_dir, changed in foreach(env):
        project_name = build_dict["name"]
        project_dir = os.path.join(env["projects_top_dir"], build_dict["path"])
        _logger.info(40 * "=")
        _logger.info("Working on [%s] in [%s]", project_name, project_dir)

        _logger.info("\tworking on [%s]", configuration)
        parallel = get_bs(env, build_dict, "parallel")
        lines_to_show = int(env["lines_to_show"])

        cmaker = cmake_batch(env, project_dir, build_dict)
        if cmaker is not None:
            ret1, status = cmaker_build_run(env, project_name, cmaker)
        else:
            sln_file = msvc_solution(env, project_dir, build_dict)
            assert sln_file is not None
            ret1, status = msvc_build_run(
                env, project_name, sln_file, configuration, build_dict, parallel, lines_to_show
            )

        ret += ret1
        build_status.append(status)
        # copy result libraries - should be here as some are deleted during the
        # compilation?!
        copy_libs(env, project_dir, build_dict)
        if changed:
            _logger.info(40 * "=" + "took: [%s]" % (time.time() - s))
            s = time.time()

    _logger.info(40 * "=")
    for status in build_status:
        _logger.info(status)
    _logger.info("Finished in [%ss]", time.time() - s)
    sys.exit(ret)
