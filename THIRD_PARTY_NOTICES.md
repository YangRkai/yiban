# 第三方依赖说明

运行依赖：Python/Tcl-Tk、NumPy、OpenCV、Pillow、cv2-enumerate-cameras。
外部程序：KataGo、所选神经网络模型、OBS Studio；GPU 后端可能需要 CUDA/cuDNN 等运行库。

本项目调用这些程序或依赖，不代表拥有它们的著作权或再分发权。正式发布时应根据实际使用版本的上游许可补充版本、来源与必要声明。这里没有替代任何上游许可证。

不随源码发布第三方客户端、可执行文件、模型、vendor 目录或 GPU 运行库。安装包的第三方组件见下方清单及随包许可证。


## Bundled CPU runtime (0.2.2)

KataGo 1.16.4 Eigen Windows x64: https://github.com/lightvector/KataGo/releases/tag/v1.16.4

Model g170e-b10c128-s1141046784-d204142634.txt.gz: https://github.com/lightvector/KataGo/releases/tag/v1.3

KataGo license is included in packaging/KataGo-LICENSE.txt and installed engine-cpu/LICENSE.txt. Upstream bundled runtime libraries are distributed with the official engine archive.
