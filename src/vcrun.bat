@echo off
rem Setup all visual studio paths
rem pushd %VS80COMNTOOLS%
rem pushd %VS90COMNTOOLS%
rem pushd %VS110COMNTOOLS%
rem pushd %VS120COMNTOOLS%
rem pushd %VS140COMNTOOLS%
rem call vsvars32.bat
rem popd 
rem Use standalone Visual Studio compiler
set BUILDER=msbuild
%BUILDER% %* "/p:PlatformToolset=v141"