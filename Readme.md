# Overview

Builds specified configuration of specified VS solutions and copies the output.
VS 2015 is a prerequisite. 

In latest versions, you need to update `vcrun.bat` with absolute path to BUILDER e.g., 
```
set BUILDER="C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\MSBuild\15.0\Bin\amd64\msbuild.exe"
```