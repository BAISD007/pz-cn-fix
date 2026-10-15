# 第三方组件说明 / Third-party notices

## 1. Noto Sans SC（字体重建的输入）

`tools/build_cn_fonts.py` 会用系统里已安装的 **Noto Sans SC** 生成位图字体。
Noto 字体由 Google 以 **SIL Open Font License 1.1** 发布：

```
Copyright 2014-2024 Adobe (http://www.adobe.com/), with Reserved Font Name 'Source'.
Copyright 2014-2024 Google LLC.
This Font Software is licensed under the SIL Open Font License, Version 1.1.
```

- 许可证全文：https://scripts.sil.org/OFL
- OFL 允许把字体嵌入、再分发（含位图形式），要求：
  1. 保留上述版权与许可声明；
  2. 若修改并再分发字体软件本身，不得使用保留字体名（Reserved Font Name）；
     本项目的生成物是位图图集，仅供《Project Zomboid》界面渲染使用。
- 本仓库**不包含** Noto 字体文件本身，脚本读取的是你机器上已安装的版本。

脚本同样支持 **MiSans**（小米，OFL）、**Microsoft YaHei**（微软，专有授权，
仅在你本机使用、不再分发的前提下可用）作为备选输入。

## 2. Project Zomboid

本项目**不包含**任何 Project Zomboid 的文件、贴图、字体或文本。
`tools/*.py` 只读取你本机已安装的游戏文件，用于：

- 读取原版 `.fnt` 的排版参数（`lineHeight` / `base` / 字号），使重建字体与原版对齐；
- 读取英文文本表以校验 key 是否存在；
- 把译文追加进你本机的 `media/lua/shared/Translate/CN/*.txt`。

《Project Zomboid》版权归 **The Indie Stone** 所有。本项目与 The Indie Stone
无任何关联，也未获其背书。若版权方有异议，请提 issue，我们会立即配合处理。

## 3. AngelCode BMFont 格式

`.fnt` / 调色板图集的格式源自 AngelCode 的 Bitmap Font Generator（免费工具）。
本项目只是生成同样格式的文件，未使用其代码。
