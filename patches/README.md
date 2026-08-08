# 本地补丁

## 001-apple-silicon-accel.patch

**可选。只在 Apple Silicon 上有意义。**

两处改动：

1. `transcribe/local.py` 加 **mlx-whisper 后端** —— 走 Apple GPU，转录明显更快
2. RapidOCR 开 **CoreML EP** —— 画面文字识别明显更快

**不打这个补丁，watch-skill 照样能跑** —— 只是转录和 OCR 用 CPU 路径，慢一些。
非 Apple Silicon 的机器**不要**打。

## 打法

```bash
git clone https://github.com/oxbshw/watch-skill.git /tmp/watch-skill
cd /tmp/watch-skill && git checkout -b local-patches
git apply /path/to/learning-video-skills/patches/001-apple-silicon-accel.patch
```

**验证**：`git apply --check <patch>` 先干跑一次。
上游变动后可能打不上 —— 那时读 patch 内容手工移植，别硬来。

## 为什么放 patch 而不放整个 vendor 目录

patch 是**差异**，vendor 是**副本**。
同一份代码存在两处，副本一定会漂移，而漂移的那一刻没人会知道。
