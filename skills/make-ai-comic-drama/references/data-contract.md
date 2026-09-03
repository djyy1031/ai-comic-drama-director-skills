# 数据约定

## 项目目录

```text
PROJECT/
├── project_config.json
├── PROJECT_STATUS.json
├── 00_INPUT/
├── 01_SCRIPT/
│   ├── normalized_script.md
│   ├── episode_map.json
│   ├── episodes/
│   └── director_requests/
├── 02_SHOTGROUPS/
│   └── EP001/
│       ├── episode_manifest.json
│       ├── director_representations/
│       └── scene_state_ledger.json
├── 03_MASTER_ASSETS/
│   ├── characters/
│   ├── scenes/
│   ├── props/
│   ├── motion/
│   ├── vfx/
│   ├── ui/
│   ├── sound/
│   ├── asset_sources.json
│   ├── asset_folder_index.json
│   └── asset_review_queue.json
├── 04_MASTER_ASSET_PROMPTS/
├── 05_SUB_ASSETS/
├── 06_PRODUCTION_TABLES/
├── 07_AUDIT/
├── 08_VIDEO_PACKAGE/
├── 09_SOUND/
└── 10_FINAL/
```

## project_config.json

必要字段：

```json
{
  "schema_version": "1.0",
  "project_name": "项目名",
  "model_profile": "seedance-2.0",
  "render_mode": "2D",
  "aspect_ratio": "9:16",
  "visual_style": "明确风格",
  "genre": {"primary": "主类型", "packs": []},
  "director_knowledge": {
    "preferred_skill": "ai-cinematic-directing-assets",
    "allow_internal_fallback": true
  },
  "episode": {"target_seconds": null, "final_max_seconds": 180},
  "subtitle_policy": {
    "generate_dialogue_subtitles": false,
    "append_to_each_language_shot": true,
    "required_language_shot_suffix": "视频严禁出现台词、内心独白与系统语音字幕。",
    "allow_story_ui_text": true
  }
}
```

`model_profile` 是模型隔离唯一开关。不得在分镜组级别临时切换。`render_mode`、`aspect_ratio`、`visual_style` 同样是项目初始化必填项，不得留空或使用未确认的默认值。

`episode.target_seconds` 默认留空。分析完原剧本后再按实际可表现内容写入预计时长；它不是必须凑满的硬下限。最终不得超过 `final_max_seconds=180`，不得用空镜、重复反应、静止画面或无意义运镜凑时长。

现成模板已按模型分开：

- `assets/project-config.seedance-2.0.template.json`
- `assets/project-config.seedance-2.5.template.json`
- `assets/episode-manifest.seedance-2.0.template.json`
- `assets/episode-manifest.seedance-2.5.template.json`

必须成对使用同一模型版本的项目配置和分集清单模板。

## episode_manifest.json

核心结构：

```json
{
  "schema_version": "1.0",
  "episode": 1,
  "model_profile": "seedance-2.0",
  "planned_final_duration_seconds": 120,
  "timeline_overhead_seconds": 0,
  "final_duration_seconds": null,
  "shot_groups": [
    {
      "shot_group_id": "EP001-SG01",
      "duration_seconds": 15,
      "duration_exception_reason": null,
      "scene_name": "综合训练教室",
      "story_event": "事件",
      "director_library_status": "AI_CINEMATIC_DIRECTING_ASSETS",
      "director_request_path": "01_SCRIPT/director_requests/EP001-SG01.json",
      "director_representation_path": "02_SHOTGROUPS/EP001/director_representations/EP001-SG01.json",
      "scene_state_ledger_path": "02_SHOTGROUPS/EP001/scene_state_ledger.json",
      "has_spoken_language": true,
      "start_blocking": {
        "world_coordinates": "真实空间位置",
        "screen_coordinates": "当前机位画面位置"
      },
      "shots": [
        {"shot_id": "S01", "start_seconds": 0, "end_seconds": 3, "purpose": "建立空间", "existence_reason": "交代出口、距离和轴线"},
        {"shot_id": "S02", "kind": "continuous_language_block", "start_seconds": 3, "end_seconds": 12, "purpose": "完整台词与自动镜头过渡", "existence_reason": "完成不可切断的情绪转折"}
      ],
      "assets": [],
      "clean_prompt": "纯净提示词"
    }
  ],
  "audits": {
    "script_fidelity": "PENDING",
    "asset_coverage": "PENDING",
    "continuity_generatability": "PENDING"
  },
  "production_ready": false,
  "sound_plan": {"status": "PENDING", "cues": []},
  "final_episode_ready": false
}
```

`planned_final_duration_seconds = 所有分镜组实际时长之和 + timeline_overhead_seconds`。

普通镜头使用各自起止时间。`kind = continuous_language_block` 表示整个区间承载一条连续对白、独白或系统语音；区间内部只描述镜头顺序和情绪节点，不再建立带子时间点的小镜头，避免音轨被重复或重启。

## 导演知识调用数据

- `01_SCRIPT/director_requests/`：保存交给 `$ai-cinematic-directing-assets` 的调用请求，包括不可修改剧情事实、原文台词、完整事件、项目配置、上一组结束状态和参考版本。
- `02_SHOTGROUPS/EP001/director_representations/`：保存专业库返回的中性导演镜头表示。它不是最终Seedance提示词，不包含全局固定画质段或资产等号绑定区。
- `02_SHOTGROUPS/EP001/scene_state_ledger.json`：保存每组入组和出组的世界空间、画面空间、人物关系、人物、环境、摄影机与剧情状态。
- 专业库未安装时，在导演表示中记录 `library_status = "FALLBACK_INTERNAL"`；成功调用时记录 `library_status = "AI_CINEMATIC_DIRECTING_ASSETS"`。禁止在未调用时伪造成功状态。
- 原文事实和台词是上游权威数据。导演表示与原文冲突时必须标记 `STALE` 并返修，禁止由导演表示覆盖原文。

## 资产字段

```json
{
  "asset_id": "内部稳定ID",
  "canonical_name": "原文标准名称",
  "asset_type": "CHARACTER",
  "version": "BASE",
  "necessity_score": 3,
  "status": "PENDING",
  "reuse_scope": "GLOBAL",
  "source": "原创或素材来源",
  "rights_status": "CONFIRMED"
}
```

允许的 `status`：`PENDING`、`IN_PROGRESS`、`READY`、`BLOCKED`、`STALE`。

动作与特效资产可选增加 `trigger_keywords`、`call_condition` 和 `forbid_condition`。关键词只用于发现候选，不能直接把资产状态改为 `READY` 或强制绑定到视频任务。项目可从 `assets/动作特效资产库模板.json` 建立登记表。

## 六类生产表

1. 母资产总表。
2. 场景机位矩阵。
3. 分镜组资产矩阵。
4. 子资产生产清单。
5. 视频输入包索引。
6. 分集声音执行表。

可复制 `assets/AI漫剧生产信息表模板.xlsx`。工作簿另含“项目总览”，用于显示模型配置、180秒上限、资产数量和可生产任务数。

表格是导演和生产人员使用的视图；JSON是状态、依赖和自动审核的权威数据。两者冲突时，先停止并核对，不自动覆盖。

## 项目状态

`PROJECT_STATUS.json` 至少记录：当前阶段、模型配置、导演知识库状态、导演表示版本、冻结分镜版本、状态账本版本、母资产版本、最后审核结果、待用户动作、更新时间。

任何上游版本变化使下游结果标记 `STALE`。

## 资产文件夹接入数据

- `asset_sources.json`：记录用户提供的资产文件夹绝对路径、接入时间和只读原则。
- `asset_folder_index.json`：记录扫描到的文件、相对路径、扩展名和自动匹配结果。
- `asset_review_queue.json`：逐项记录标准资产名称、候选文件、匹配状态、内容审核状态、审核证据、问题和返修建议。
- 自动扫描不得直接把资产状态改成 `READY`。只有实际内容审核通过后才能同步资产表状态。

## 校验阶段

- `planning`：配置、模型隔离、每集180秒上限、分镜组时长、普通镜头时间、连续语言表演块外层时间、字幕结尾和明确命名。
- `production`：包含planning，并要求三轮审核为PASS、必须资产READY、`production_ready=true`。
- `final`：包含production，并要求真实成片时长不超过180秒、声音执行表READY、授权明确、`final_episode_ready=true`。
