VERSION=1.0.86
DISTRIBUTION=ubuntu-disco

if [ `python3 --version | awk '{print $2}' | grep -c "^3.7"` -eq 1 ]
then
  PYTHON3_PACKAGE_LOCATION=usr/local/lib/python3.7/dist-packages/

  rm -rf $PYTHON3_PACKAGE_LOCATION/manmon
  rm -rf $PYTHON3_PACKAGE_LOCATION/manmon-plugins
  mkdir -p $PYTHON3_PACKAGE_LOCATION/manmon
  mkdir -p $PYTHON3_PACKAGE_LOCATION/manmon-plugins
  cp -p ../../manmon/*.py $PYTHON3_PACKAGE_LOCATION/manmon
  cp -p ../../manmon-plugins/*.py $PYTHON3_PACKAGE_LOCATION/manmon-plugins
  python3 -m compileall $PYTHON3_PACKAGE_LOCATION/manmon
  python3 -m compileall $PYTHON3_PACKAGE_LOCATION/manmon-plugins
#  rm -f $PYTHON3_PACKAGE_LOCATION/manmon/*.py
#  rm -f $PYTHON3_PACKAGE_LOCATION/manmon-plugins/*.py
  cd $PYTHON3_PACKAGE_LOCATION/manmon/__pycache__
  rename 's/\.cpython-37//' *.pyc
  mv *.pyc ../
  cd ..
  rmdir __pycache__
  cd ../manmon-plugins/__pycache__
  rename 's/\.cpython-37//' *.pyc
  mv *.pyc ../
  cd ..
  rmdir __pycache__
  cd ../../../../../../ 
  mkdir -p manmon-agent-${DISTRIBUTION}-${VERSION}-1
  mv usr manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr
  cp -rp DEBIAN manmon-agent-${DISTRIBUTION}-${VERSION}-1/DEBIAN
  perl -p -i -e "s/Package: manmon-agent/Package: manmon-agent-${DISTRIBUTION}/" manmon-agent-${DISTRIBUTION}-${VERSION}-1/DEBIAN/control
  perl -p -i -e "s/Version: 1.0-1/Version: ${VERSION}-1/" manmon-agent-${DISTRIBUTION}-${VERSION}-1/DEBIAN/control
  mkdir -p manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/bin/
  cp -p ../../bin/python3_start.sh manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/bin/mmagent
  chmod +x manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/bin/mmagent
  cp -p ../../bin/python3_start_uploader.sh manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/bin/mmagent-uploader
  cp -p ../../bin/manmon_save_hostgroup_key manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/bin/
  cp -p ../../bin/manmon_save_host_key manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/bin/ 
  chmod +x manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/bin/manmon_save_hostgroup_key
  chmod +x manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/bin/manmon_save_host_key
  chmod +x manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/bin/mmagent-uploader
  mkdir -p usr/lib/systemd/system/
  cp -p ../../systemd/manmon-agent.service usr/lib/systemd/system/manmon-agent.service
  cp -p ../../systemd/manmon-agent-uploader.service usr/lib/systemd/system/manmon-agent-uploader.service
  mv usr/lib manmon-agent-${DISTRIBUTION}-${VERSION}-1/usr/
  rmdir usr
  mkdir -p manmon-agent-${DISTRIBUTION}-${VERSION}-1/var/lib/manmon
  cp -p ../mib.db manmon-agent-${DISTRIBUTION}-${VERSION}-1/var/lib/manmon/
  dpkg -b manmon-agent-${DISTRIBUTION}-${VERSION}-1
  rm -rf manmon-agent-${DISTRIBUTION}-${VERSION}-1
else
  print "Wrong python version"
fi


