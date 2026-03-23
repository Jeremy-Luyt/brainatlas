@ echo off
set subpath=Z:\2.postgrad\22-hhm\deep_data\val\fhua\mri\
echo DIR=%subpath%
setlocal enabledelayedexpansion
rem set foldername=''
for /f %%i in (dataf.txt)  do (
echo=s
set foldername=%%i
set subimg=%subpath%\!foldername!
echo SUBIMG=!subimg!
set savepath=Z:\2.postgrad\22-hhm\deep_data\val\fhua\mri\!foldername!\ccf\
echo SAVEPATH=!savepath!
..\binary\win64_bin\local_registration_2017.exe -p config/config.txt -s !subimg!\brain.v3draw  ^
^ -l E:\fmost_demo\examples\target\25um_568\target_landmarks/high_landmarks.marker -g E:\fmost_demo\examples\target\25um_568/ -o !savepath! -u 0 
)
PAUSE