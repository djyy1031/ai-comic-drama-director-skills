# GPT网页版场景资产批次

## 总任务

根据下面的全文场景总框架，生成 {{image_count}} 张彼此独立、可分别保存的场景资产图片。每条单图任务只对应一张图片，输出顺序必须与资产清单一致。

严禁把多个画面合成九宫格、十宫格、拼贴、分屏、联系表、故事板或一张图中的多个镜头。{{image_count}} 张图表现的是摄影机在同一个真实场景中移动，不是重新设计 {{image_count}} 个不同地点。

工作流模式：{{workflow_mode}}

- LOCKED_PRODUCTION：必须使用 {{anchor_image_ids}} 对应的已审核锚点图作为参考。
- ONE_CLICK_DRAFT_SET：依靠下面冻结的文字框架并行生成；不得宣称后图已经实时参考前图。返回后需要审核、选定锚点并返修漂移图片。

## 全剧统一色卡

色卡版本：{{color_bible_version}}

色块与使用部位：
{{color_swatches_and_roles}}

统一后期基准：
{{grade_profile}}

禁止色偏与颜色：
{{forbidden_color_casts}}

所有图片必须继承同一版色卡。HEX或RGB用于后期和沟通，生图时同时遵守对应的色名、材质与光照关系。

## 全文场景总框架

场景家族：{{scene_family_name}}

全文用途与后续约束：
{{full_script_scene_usage}}

区域与空间连接：
{{spatial_model}}

统一视觉DNA：
{{visual_dna}}

全局必须存在：
{{family_must_have}}

全局禁止出现：
{{family_must_not_have}}

允许合理补全及边界：
{{family_allowed_enrichment}}

基础空景不应包含的状态陈设、镜头临时道具和角色持物：
{{excluded_non_base_items}}

基础时间与天气：{{base_time_weather}}

基础资产一律按白天制作；未指定天气时采用晴朗白天。若原文只在一种天气出现，则白天母资产采用该天气。黄昏、夜晚或其他天气另作派生变体，不改变本批资产的场景设计。

共同状态：
{{shared_state}}

## 独立图片任务

按以下格式填写1至10条。每条必须完整，不得写“同上”。

### 图片 {{output_index}}：{{canonical_name}}

- 资产ID：{{asset_id}}
- 摄影机位置：{{camera_position}}
- 观察方向：{{looking_direction}}
- 可见连接口：{{visible_connections}}
- 与相邻图片共享的固定锚点：{{shared_anchors}}
- 当前图片必须出现：{{must_have}}
- 当前图片禁止出现：{{must_not_have}}
- 允许合理补全：{{allowed_enrichment}}
- 继承且绝不改变：{{invariant_from_parent}}
- 完整单图提示词：{{full_prompt}}

## 后续时间与天气变体表

基础图片生成并审核后，再按下列登记逐条制作。每条必须填写引用的白天资产ID、使用集数和完整派生提示词。

### 变体 {{variant_index}}：{{target_time_weather}}

- 变体ID：{{variant_id}}
- 引用白天资产ID：{{reference_asset_id}}
- 使用集数：{{episode_usage}}
- 原文依据：{{source_evidence}}
- 只允许改变：{{allowed_environment_delta}}
- 必须保持不变：摄影机、构图、建筑格局、连接关系、门窗、楼梯、家具、固定物、物件数量与位置、材质纹理、磨损和全剧色卡版本
- 完整派生提示词：{{variant_prompt}}

## 输出核对

- 返回数量必须为 {{image_count}} 张独立图片。
- 每张图片只能对应一个资产ID，不得合并。
- 场景结构、材质、固定物和连接方向必须统一。
- 每张基础图必须使用白天环境并继承色卡版本 {{color_bible_version}}。
- 时间或天气变体必须引用已审核白天图，只改光线、天气及其直接物理反馈。
- 若无法独立返回多张图片，直接说明限制，不得用网格拼图替代。
