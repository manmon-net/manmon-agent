%define name manmon-agent
%define version 1.0
%define unmangled_version 1.0
%define release 90_el7

Summary: Manmon monitoring agent
Name: %{name}
Version: %{version}
Release: %{release}
Source0: https://github.com/manmon-net/manmon-agent/archive/master.zip
License: Commercial
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Tomi Malkki <tomi@manmon.net>
Url: https://manmon.net/
Requires: python2-crypto
Requires: python-requests
Requires: python-httplib2
Requires: manmon-key
Requires: manmon-conf
Requires: python-lxml

%description
Monitoring agent

%prep 
%setup -n manmon-agent-master

%build
python setup.py build

%install
perl -p -i -e "s/    return int(value)/    return long(value)/" manmon/get_long.py
python setup.py install -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
mkdir -p %{buildroot}/usr/lib/systemd/system/
install -p -m 664 systemd/manmon-agent.service %{buildroot}/usr/lib/systemd/system/
install -p -m 664 systemd/manmon-agent-uploader.service %{buildroot}/usr/lib/systemd/system/
mkdir -p %{buildroot}/var/lib/manmon
install -p -m 664 pkg/mib.db %{buildroot}/var/lib/manmon/
mkdir -p %{buildroot}/usr/bin/
install -p -m 755 bin/python2_start.sh %{buildroot}/usr/bin/mmagent
install -p -m 755 bin/python2_start_uploader.sh %{buildroot}/usr/bin/mmagent-uploader
install -p -m 755 bin/manmon_save_host_key %{buildroot}/usr/bin/manmon_save_host_key
install -p -m 755 bin/manmon_save_hostgroup_key %{buildroot}/usr/bin/manmon_save_hostgroup_key
perl -p -i -e 's/python3/python' %{buildroot}/usr/bin/manmon_save_host_key
perl -p -i -e 's/python3/python' %{buildroot}/usr/bin/manmon_save_hostgroup_key
rm -f %{buildroot}/usr/lib/python2.7/site-packages/manmon/*.py
rm -f %{buildroot}/usr/lib/python2.7/site-packages/manmon-plugins/*.py
mkdir -p %{buildroot}/etc/manmon-plugins.d

%pre
if ! id -u mmagent > /dev/null 2>&1; then
  adduser -m mmagent
fi
if [ "$1" -eq 2 ]
then
  if systemctl -q is-active manmon-agent 
  then
    touch /var/lib/manmon/agent-was-running
    systemctl stop manmon-agent 
  fi
  if systemctl -q is-active manmon-agent-uploader
  then
    touch /var/lib/manmon/uploader-was-running
    systemctl stop manmon-agent-uploader
  fi
fi

%post
systemctl -q daemon-reload
if systemctl -q is-enabled manmon-agent || [ -f /var/lib/manmon/agent-was-running ]
then
  rm -f /var/lib/manmon/agent-was-running
  systemctl start manmon-agent
fi
if systemctl -q is-enabled manmon-agent-uploader || [ -f /var/lib/manmon/uploader-was-running ]
then
  rm -f /var/lib/manmon/uploader-was-running
  systemctl start manmon-agent-uploader
fi

%preun
if [ "$1" -eq 0 ]
then
  if systemctl -q is-active manmon-agent
  then
    systemctl -q stop manmon-agent
  fi
  if systemctl -q is-active manmon-agent-uploader
  then
    systemctl -q stop manmon-agent-uploader
  fi
fi

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
/usr/bin/mmagent
/usr/bin/manmon_save_host_key
/usr/bin/manmon_save_hostgroup_key
/usr/bin/mmagent-uploader
/usr/lib/python2.7/site-packages/manmon/*.pyc
/usr/lib/python2.7/site-packages/manmon/*.pyo
/usr/lib/python2.7/site-packages/manmon-plugins/*.pyc
/usr/lib/python2.7/site-packages/manmon-plugins/*.pyo
/usr/lib/python2.7/site-packages/manmon_agent-1.0-py2.7.egg-info
%dir /etc/manmon-plugins.d/
/usr/lib/systemd/system/manmon-agent.service
/usr/lib/systemd/system/manmon-agent-uploader.service
/var/lib/manmon/mib.db

