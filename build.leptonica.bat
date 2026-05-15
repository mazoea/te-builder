cd ..

echo "Cloning projects"
REM git clone git@github.com:mazoea/cpp-template.git
git clone git@github.com:mazoea/te-external.git
git clone git@github.com:mazoea/te-builder.git
git clone git@github.com:mazoea/te-external-leptonica.git

pause

echo "Building basic libraries"
cd te-external
REM not required by default
REM xcopy /S /I _vsprops-base ..\cpp-template\projects\vsprops-base
python create_links.py
cd ../te-builder/src
python main.py --settings=externals.basic.json
cd ..
pause


echo "Building leptonica"
cd te-external-leptonica
python create_links.py
cd ..
cd te-builder/src
python main.py --settings=leptonica.json
cd ..
pause