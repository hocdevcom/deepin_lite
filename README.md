# Deepin Lite

Bản dựng thử nghiệm Deepin amd64 tối giản, với GitHub Actions tạo Live ISO.
Giữ desktop Deepin (DDE), file manager, terminal, mạng và âm thanh. Không dùng
metapackage `dde` / `deepin-desktop-environment` vì chúng kéo theo nhiều ứng dụng.

## Phạm vi mã nguồn

- Nền hệ thống: gói nhị phân có chữ ký từ kho chính thức Deepin `beige`, chỉ
  `main` và `community`; không thêm kho `commercial`, App Store hay Linglong.
- Biên dịch **deepin-desktop-base**, **dde-api**, **dde-session**, **dde-daemon**, **dde-file-manager** và
  **dde-control-center** từ
  [linuxdeepin](https://github.com/linuxdeepin), khóa commit và SHA256 trong
  `config/upstream.lock.json`. Đây **không phải** bản biên dịch toàn bộ Deepin từ nguồn.
- Sửa packaging của dde-api để bỏ phụ thuộc bắt buộc vào font CJK/Unifont.
  Không giả lập gói phụ thuộc, không dùng `--force-depends`.
- Build dependency nằm trong chroot riêng; build chạy dưới user thường với
  fakeroot và có changelog downstream riêng. Không đưa build dependency vào ISO.
- Test khi build gói có session D-Bus riêng và màn hình Xvfb; `dbus-x11`, Xvfb,
  xauth chỉ cài trong builder. Không dùng `nocheck` để bỏ qua test thất bại.
  Log từng gói nằm trong `source-build-<tên-gói>.log` ở artifact reports.
- Builder cài `deepin-desktop-base` để test đọc được `/etc/os-version`, cùng
  `grub-common`, `librsvg2-bin` và Unifont cho test theme. ISO cài DEB desktop-base
  đã build lại, bỏ phụ thuộc font thừa và App Store config; giữ postinst và
  update-alternatives của upstream để dpkg quản lý metadata hệ điều hành.
- Suite `beige` là nhánh kho đã chọn để dựng hệ thống mutable bằng APT;
  dự án không tuyên bố tương đương ISO immutable Deepin 25 chính thức.

## Loại bỏ và giảm dung lượng

`config/deny-packages.txt` là danh sách **gỡ bằng apt purge**, bao gồm AI/UOS AI,
cloud sync, Deepin ID/UnionID, App Store, Linglong, WeChat/QQ, Baidu, WPS, Sogou,
ứng dụng thương mại `com.*`/`cn.*`, ứng dụng phụ và font Trung Quốc.
Sau khi cài các gói tối thiểu, build purge cả gói và conffile trong danh sách,
autoremove phụ thuộc thừa rồi xác nhận desktop bắt buộc vẫn được cài.
Không dùng negative APT pins, D-Bus deny hay systemd mask để giả thay việc xóa.

Các tích hợp nhúng được xóa tại nguồn trong `scripts/source_cleanup.py`:

- **dde-daemon:** xóa bảy adapter cloud sync, thư viện dsync, API xuất/nhập
  cấu hình mạng cho cloud, đổi mật khẩu qua UnionID và module EventLog
  và các action bàn phím gọi iFlytek AI.
- **Control Center:** xóa UI cũ chứa UnionID/reset mật khẩu trực tuyến;
  xóa plugin Accounts/cloud sync, Deepin ID, Common Info, System Info và Update.
  Quản lý user Linux cục bộ vẫn còn qua CLI; các trang GUI nói trên không còn.
- **File Manager:** xóa mã gọi cloud helper để hỏi vendor developer mode.
  Chế độ vendor này không được cung cấp; quản lý tệp cục bộ vẫn được giữ.

`scripts/verify-debs.py` kiểm tra payload và maintainer script của từng DEB.
`scripts/image_cleanup.py` chỉ đọc image, quét cả binary và cấu hình cho
các định danh D-Bus AI/cloud/ID/EventLog,
kể cả chuỗi UTF-16. Nếu còn dấu vết thực thi đã biết, build thất bại thay vì
che bằng quy tắc chặn. Báo cáo nằm trong `removal-audit.txt` và
`purged-packages.txt` và `deb-audit.txt`. Nếu còn code trong gói lõi, phải sửa
nguồn và build lại; không tự xóa file thuộc gói sau khi cài. UADP cục bộ được giữ
vì upstream dùng nó để mã hóa/lưu khóa qua Secret Service; nó không tự động là
cloud/AI chỉ vì được Deepin phát triển. Giấy phép/copyright được giữ nguyên.

“Bỏ app China” ở đây là bỏ các ứng dụng/dịch vụ tùy chọn trên và tích hợp đã xác
định; giữ lõi giao diện DDE. Kiểm tra dựa trên định danh đã biết không chứng minh
đã tìm ra mọi mã nhúng hoặc mọi lưu lượng mạng. Chưa được phép coi image là đã
kiểm toán toàn diện trước khi build thành công và kiểm thử thực tế.

Giữ locale Anh/Việt, một theme Bloom, không browser/office/games/printer/AI models.
Xóa cache; dùng path-exclude/path-include của dpkg để giảm tài liệu và locale
ngay khi cài gói; giữ copyright/license và nén SquashFS XZ 1 MiB.
Không xóa driver/firmware một cách mù quáng. Bản hiện tại không bổ sung bộ firmware
Wi-Fi proprietary lớn; một số phần cứng cần cài firmware sau.
Không cam kết số GB hoặc “nhỏ nhất tuyệt đối” trước khi build và đo thực tế.

## Build trên GitHub Actions

1. Đưa toàn bộ repository này lên GitHub, nhánh `main`.
2. Mở **Actions → Deepin Lite ISO → Run workflow**. Push vào main cũng tự build.
3. Khi source build, audit và kiểm tra live desktop đều thành công, tải artifact
   `deepin-lite-amd64-<run>`: ISO, SHA256SUMS, các gói DEB đã biên dịch và
   source package tương ứng trong `sources/`.
4. Artifact reports có `packages.tsv`, `applications.txt`, `services.txt`,
   `size-report.txt`, nguồn đã khóa, InRelease và log QEMU/build.

PR kiểm tra cấu hình/scripts và áp dụng các sửa đổi lên nguồn đã khóa. Workflow không cần PAT hay secrets.
Quyền mặc định `contents: read`; không tự phát hành GitHub Release.
Artifact ISO giữ 7 ngày, logs 14 ngày. Lần đầu có thể mất 1–3 giờ và cần đủ
dung lượng trống cho hai chroot; nếu hosted runner hết đĩa, dùng runner lớn hơn.

## Build trên Ubuntu 24.04 amd64

```bash
sudo apt-get update
sudo apt-get install -y debootstrap gnupg curl ca-certificates squashfs-tools \
  xorriso grub-pc-bin grub-efi-amd64-bin grub-common mtools python3 qemu-system-x86
sudo bash scripts/build.sh
sudo bash scripts/smoke.sh
```

Cần checkout mới, chưa có `.work/` hoặc `dist/`; script không tự xóa thư mục cũ.
Chỉ chạy build trong VM/runner chuyên dụng vì cần root và chroot mount.
APT kiểm tra chữ ký với keyring upstream được khóa checksum, không dùng
`trusted=yes`, `--allow-unauthenticated` hoặc `--no-check-gpg`.
Nguồn GitHub đã khóa nhưng kho APT vẫn biến đổi: manifest/InRelease được lưu để
truy vết, chưa bảo đảm tái lập bit-for-bit. Các gói tự build được pin `+lite3`;
muốn cập nhật chúng cần cập nhật source lock và build lại.

Xem [báo cáo rà soát build và gỡ gói](docs/build-removal-review.md) cho phạm vi
đối chiếu upstream và các bước còn chưa kiểm chứng.

## Trạng thái và giới hạn kiểm thử

Đây là **Live ISO thử nghiệm**, chưa có trình cài đặt vào ổ đĩa. Boot dùng
`live-config`, user `live`, quyền sudo dành cho phiên live. Không dùng như một
hệ thống đã cài hoặc để chứa dữ liệu nhạy cảm trước khi kiểm tra.

ISO có GRUB BIOS/UEFI; Secure Boot chưa được hỗ trợ. CI kiểm tra boot metadata,
khởi động kernel/initrd của ISO bằng QEMU TCG và đợi NetworkManager, LightDM,
`dde-shell` cùng `dde-desktop` hoạt động. CI chưa kiểm chứng đường boot firmware
BIOS/UEFI thực, thao tác giao diện, mạng ra ngoài hoặc cài đặt vào đĩa.
Máy Windows soạn dự án này chưa có Linux runtime nên chưa build/chạy ISO tại chỗ;
chỉ được coi là build thành công sau khi workflow thực tế xanh.

Các thành phần Deepin giữ giấy phép upstream. Khi phân phối image công khai,
cần đáp ứng nghĩa vụ cung cấp corresponding source của các thành phần liên quan;
các gói nguồn tự sửa được lưu trong artifact và có thể tái tạo bằng source lock
và prepare-sources.py.

Nguồn tham khảo: [Deepin GitHub](https://github.com/linuxdeepin),
[kho gói](https://www.deepin.org/en/mirrors/packages/),
[keyring upstream](https://github.com/linuxdeepin/deepin-keyring).
