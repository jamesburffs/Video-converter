# RPM spec for VidKonverter - packages the prebuilt PyInstaller binary from
# dist/ (run packaging/build.py first) rather than compiling from source, so
# there's no %build step and no BuildRequires on the Python/Qt toolchain.
#
# project_root and the version are passed in via environment variables by
# packaging/build_rpm.py, which also sets up the rpmbuild tree - this spec
# isn't meant to be run through a normal `rpmbuild -ba` from an SRPM.

%global project_root %{getenv:VK_PROJECT_ROOT}

Name:           vidkonverter
Version:        %{getenv:VK_VERSION}
Release:        1%{?dist}
Summary:        Convert video files with ffmpeg
License:        GPLv3
URL:            https://github.com/cooleryoungerbrother/vidkonverter
BuildArch:      x86_64

# The PyInstaller binary bundles its own Python/Qt/etc - rpm's automatic
# dependency scanner would otherwise inspect it and produce bogus/unhelpful
# Requires (or just take a long time on a 170MB+ binary).
AutoReqProv:    no
Recommends:     ffmpeg

%description
VidKonverter is a desktop GUI for converting and batch-converting video
files with ffmpeg - container/codec selection, crop, trim, and alpha
channel handling.

%install
rm -rf %{buildroot}
install -Dm755 %{project_root}/dist/VidKonverter %{buildroot}%{_bindir}/vidkonverter
install -Dm644 %{project_root}/packaging/vidkonverter.desktop %{buildroot}%{_datadir}/applications/vidkonverter.desktop
install -Dm644 %{project_root}/videoconverter/icons/vidkonverter-app-icon.png %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/vidkonverter.png
install -Dm644 %{project_root}/LICENSE %{buildroot}%{_datadir}/licenses/vidkonverter/LICENSE

%files
%{_bindir}/vidkonverter
%{_datadir}/applications/vidkonverter.desktop
%{_datadir}/icons/hicolor/512x512/apps/vidkonverter.png
%license %{_datadir}/licenses/vidkonverter/LICENSE

%changelog
* Thu Sep 17 2026 VidKonverter <james@farfromsquare.io> - 1.0.0-1
- Initial package
