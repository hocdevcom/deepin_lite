# Deepin Lite

Bản dựng thử nghiệm Deepin amd64 tối giản, với GitHub Actions tạo Live ISO.
Giữ desktop Deepin (DDE), file manager, terminal, mạng và âm thanh. Không dùng
metapackage `dde` / `deepin-desktop-environment` vì chúng kéo theo nhiều ứng dụng.

## Phạm vi mã nguồn

- Nền hệ thống: gói nhị phân có chữ ký từ kho chính thức Deepin `beige`, chỉ
  `main` và `community`; không thêm kho `commercial`, App Store hay Linglong.
- Biên dịch **dde-api 6.0.13** và **dde-session 1.2.13** từ
  [linuxdeepin](https://github.com/linuxdeepin), khóa commit và SHA256 trong
  `config/upstream.lock.json`. Đây **không phải** bản biên dịch toàn bộ Deepin từ nguồn.
- Sửa packaging của dde-api để bỏ phụ thuộc bắt buộc vào font CJK/Unifont.
  Không giả lập gói phụ thuộc, không dùng `--force-depends`.
- Các build dependency nằm trong chroot riêng, không đưa vào ISO.
- Suite `beige` là nhánh kho đã chọn để dựng hệ thống mutable bằng APT;
  dự án không tuyên bố tương đương ISO immutable Deepin 25 chính thức.

## Loại bỏ và giảm dung lượng

`config/deny-packages.txt` chặn AI/UOS AI, cloud sync, UnionID, App Store,
Linglong, WeChat/QQ, Baidu, WPS, Sogou, ứng dụng thương mại `com.*`/`cn.*`,
ứng dụng phụ Deepin, font Trung Quốc và gói debug/development.
“Bỏ app China” được hiểu là bỏ ứng dụng và dịch vụ tùy chọn nói trên; giữ lõi DDE
do Deepin phát triển để vẫn có giao diện Deepin. Không thể vừa xóa mọi mã nguồn
có xuất xứ Trung Quốc vừa giữ DDE.

APT dùng negative pins trước khi cài, tắt Recommends/Suggests. Build **thất bại**
nếu phụ thuộc bắt buộc xung đột chính sách hoặc manifest còn gói bị cấm.
D-Bus chặn một số tên cloud/AI đã biết; các systemd unit có tên tương ứng bị mask.
Đây là chính sách theo danh sách đã biết, chưa phải kiểm toán toàn bộ mã nguồn,
plugin nhúng hoặc lưu lượng mạng. Cần xem báo cáo và kiểm tra mạng trong VM trước
khi kết luận hệ thống không còn mọi kết nối dịch vụ Deepin.

Giữ locale Anh/Việt, một theme Bloom, không browser/office/games/printer/AI models.
Xóa cache, tài liệu phụ, bản dịch dư; giữ copyright/license và nén SquashFS XZ 1 MiB.
Không xóa driver/firmware một cách mù quáng. Bản hiện tại không bổ sung bộ firmware
Wi-Fi proprietary lớn; một số phần cứng cần cài firmware sau.
Không cam kết số GB hoặc “nhỏ nhất tuyệt đối” trước khi build và đo thực tế.

## Build trên GitHub Actions

1. Đưa toàn bộ repository này lên GitHub, nhánh `main`.
2. Mở **Actions → Deepin Lite ISO → Run workflow**. Push vào main cũng tự build.
3. Khi source build, audit và kiểm tra live desktop đều thành công, tải artifact
   `deepin-lite-amd64-<run>`: ISO, SHA256SUMS, hai gói DEB đã biên dịch và
   source package tương ứng trong `sources/`.
4. Artifact reports có `packages.tsv`, `applications.txt`, `services.txt`,
   `size-report.txt`, nguồn đã khóa, InRelease và log QEMU/build.

PR chỉ kiểm tra cấu hình/scripts. Workflow không cần PAT hay secrets.
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
truy vết, chưa bảo đảm tái lập bit-for-bit. Hai gói tự build được pin `+lite1`;
muốn cập nhật chúng cần cập nhật source lock và build lại.

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
hai gói nguồn tự sửa được lưu trong artifact và có thể tái tạo bằng source lock
và prepare-sources.py.

Nguồn tham khảo: [Deepin GitHub](https://github.com/linuxdeepin),
[kho gói](https://www.deepin.org/en/mirrors/packages/),
[keyring upstream](https://github.com/linuxdeepin/deepin-keyring).
