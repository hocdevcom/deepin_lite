# Rà soát build và gỡ gói — 03/11/2026

Kết luận: đóng gói thành phần theo hệ Debian của Deepin là hướng phù hợp.
Tuy nhiên, dự án là bản fork tùy biến và Live ISO tự dựng, không phải pipeline
ISO chính thức hay bản Deepin 25 immutable. Chưa có lần build toàn bộ/boot thành
công, nên chưa chứng nhận hoạt động hoặc đã loại sạch mọi tích hợp trực tuyến.

## Đối chiếu và sửa

| Hạng mục | Kết quả rà soát và cách xử lý |
|---|---|
| Build DEB | Upstream cung cấp `debian/control`, `debian/rules`, hướng dẫn cài build-dep và chạy dpkg-buildpackage. Giữ các file đóng gói này; dùng apt-get build-dep trên thư mục source để giải Build-Depends. |
| Quyền build | Chroot/apt cần root; biên dịch và test chuyển sang user `builder`, tạo DEB bằng fakeroot. |
| Phiên bản downstream | Thêm entry changelog `+lite3`, giữ nguyên entry/tác giả upstream. Revision lưu trong source lock. |
| Metadata OS | Không chép `/etc/os-version` bằng tay nữa. Build lại và cài gói deepin-desktop-base; giữ postinst/update-alternatives, bỏ App Store config và phụ thuộc font thừa tại nguồn. |
| Gói AI/cloud riêng | apt purge để chạy maintainer scripts và gỡ conffile, autoremove phụ thuộc, sau đó apt-get check/dpkg --audit và kiểm tra các gói desktop bắt buộc. |
| Tích hợp nhúng | Sửa nguồn ở commit cố định, build lại DEB và source package. Đây là patch downstream; không tuyên bố Deepin cung cấp tùy chọn chính thức để gỡ tất cả AI/cloud. |
| File thuộc gói | Bỏ thao tác xóa theo regex sau khi cài. Audit chỉ đọc và dừng build khi còn tích hợp; phải sửa gói/nguồn thay vì làm sai trạng thái dpkg. |
| UADP | Khôi phục UADP và các API khóa cục bộ. Mã upstream dùng Secret Service và mã hóa/lưu khóa; không có cơ sở coi toàn bộ UADP là cloud/telemetry. |
| Giảm tài liệu/locale | Dùng cơ chế path-exclude/path-include của dpkg khi cài. Không xóa tùy tiện file trong /usr sau cài. |
| Test | Giữ test/packaging upstream. Builder có OS metadata, D-Bus, Xvfb, GRUB tools và SVG converter; giữ log từng gói. File Manager upstream đặt nocheck, nên không tuyên bố gói này đã chạy unit test. |
| Kiểm tra DEB | Giải nén DEB vào thư mục tạm và quét payload/maintainer scripts trước khi cài vào image; yêu cầu đủ các source đã khóa, đúng revision downstream. |

## Những gì vẫn cần xác nhận trên runner Linux

1. Build và test đầy đủ cả tám source package, đặc biệt các API và plugin sau sửa.
2. APT giải được phụ thuộc của các DEB sửa trên cùng kho beige; không xóa gói lõi.
3. Audit payload của DEB và rootfs không còn định danh AI/cloud đã biết.
4. QEMU kiểm tra phiên DDE, file manager, mạng, âm thanh và local login/lock.
5. Smoke test đã chuyển sang boot chính ISO qua BIOS và OVMF UEFI, bao gồm
   GRUB và live initramfs. Cần kiểm chứng kết quả runner.
6. Theo dõi lưu lượng mạng/activation trong phiên hoạt động để tìm tích hợp chưa
   được nhận diện. Quét tên/chuỗi không thể thay cho kiểm toán toàn bộ mã nguồn.

Kho APT chưa được snapshot; manifest và InRelease hỗ trợ truy vết nhưng chưa đủ
tái lập bit-for-bit. Ubuntu debootstrap dùng script bookworm cho suite beige đã
qua bootstrap ở lần chạy trước, nhưng cách ghép Live ISO này vẫn là lựa chọn
của dự án, chưa được đối chiếu như pipeline ISO chính thức của Deepin.

Control Center hiện bỏ cả UI cũ và một số plugin có cloud integration. Vì vậy
Accounts/System Info/Common Info/Update GUI không còn; quản lý user Linux cục
bộ dùng CLI. Đây là đánh đổi chức năng đã biết, không phải bảo đảm tương đương
desktop upstream. ISO hiện cũng chưa có trình cài đặt lên ổ đĩa.

## Nguồn đối chiếu chính

- [Deepin Control Center: hướng dẫn đóng gói](https://github.com/linuxdeepin/dde-control-center/blob/6.0.78.1/README.md)
- [Control Center: cấu hình CMake tại revision dùng trong dự án](https://github.com/linuxdeepin/dde-control-center/blob/6.0.78.1/CMakeLists.txt)
- [UADP agent: Secret Service và lưu khóa cục bộ](https://github.com/linuxdeepin/dde-daemon/blob/6.0.49/session/uadpagent1/uadpagent.go)
- [deepin-desktop-base: nguồn metadata và packaging](https://github.com/linuxdeepin/deepin-desktop-base/tree/2024.07.26)
- [apt-get: purge, autoremove và check](https://manpages.debian.org/testing/apt/apt-get.8.en.html)
- [dpkg: path-exclude/path-include](https://manpages.debian.org/testing/dpkg/dpkg.1.en.html)
- [Workflow đóng gói dùng chung của linuxdeepin](https://github.com/linuxdeepin/.github/blob/master/.github/workflows/build-distribution.yml)

Các đánh giá về mã nguồn dựa trên đúng tag/commit trong source lock. Không suy
ra chức năng chỉ từ nguồn gốc quốc gia, tên nhà phát triển hoặc từ khóa chung.

## Kiểm chứng đã thực hiện tại máy soạn

- Tải lại và xác minh checksum cả tám source archive; áp dụng thành công các sửa đổi.
- Kiểm tra Go parser bằng gofmt; xác nhận giữ UADP/API khóa cục bộ, bỏ adapter
  cloud và App Store config tại nguồn; changelog downstream đúng revision lite3.
- ShellCheck, Bash syntax, Python compile và bốn unit test về package/audit đạt.
- Chưa chạy full compile/test DEB, dpkg extraction audit thực tế hay QEMU trên máy
  Windows này. Những phần đó mới được bổ sung thành kiểm tra trong Actions.

## Tiến độ runner Linux

Run 41580560850 đã build và audit thành công 7/8 source package; File Manager
được build lại trong run 41582583426 sau khi bổ sung dịch vụ xác thực cục bộ
được khóa checksum. Chưa coi đây là kết quả ISO hoàn chỉnh. Artifact tái sử dụng
phải thuộc job đã đạt và source archive phải khớp source chuẩn bị từ bản vá hiện tại.
