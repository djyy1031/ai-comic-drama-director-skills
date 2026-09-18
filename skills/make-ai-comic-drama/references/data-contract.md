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
  "global_prompt_profile": "已锁定全局提示词版本",
  "genre": {"primary": "主类型", "packs": []},
  "director_knowledge": {
    "preferred_skill": "ai-cinematic-directing-assets",
    "allow_internal_fallback": true
  },
  "episode": {
    "target_seconds": null,
    "normal_min_seconds": 90,
    "final_max_seconds": 180,
    "adaptive_to_script": true,
    "preferred_max_shot_groups": null
  },
  "subtitle_policy": {
    "generate_dialogue_subtitles": false,
    "append_to_each_language_shot": true,
    "required_language_shot_suffix": "视频严禁出现台词、内心独白与系统语音字幕。",
    "allow_story_ui_text": true
  }
}
```

`model_profile` 是模型隔离唯一开关。不得在分镜组级别临时切换。`render_mode`、`aspect_ratio`、`visual_style`、`global_prompt_profile` 同样是项目初始化必填项，不得留空或使用未确认的默认值。

项目开始时先询问用户希望每集大概多长。`episode.target_seconds` 记录用户指定的130秒等软目标；用户没有特别要求时保持 `null`，按 `normal_min_seconds=90` 至 `final_max_seconds=180` 的正常范围由剧情决定。`adaptive_to_script=true` 表示目标不能强制凑满：内容少可靠近90秒，内容多可在180秒内延长。不得用空镜、重复反应、静止画面或无意义运镜凑时长。

`preferred_max_shot_groups` 默认留空；只有用户明确提出组数偏好时才填写。两个模型共用事件分组规则，仅单组时长上限分别为15秒和30秒；不存在模型专属最低时长、镜数或30秒填满目标。

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
  "schema_version": "1.1",
  "episode": 1,
  "model_profile": "seedance-2.0",
  "planned_final_duration_seconds": 120,
  "duration_planning_reason": "根据剧情密度与用户软目标说明本集时长依据",
  "duration_deviation_reason": null,
  "shot_group_count_exception_reason": null,
  "timeline_overhead_seconds": 0,
  "final_duration_seconds": null,
  "language_units": [
    {
      "language_id": "DIA01",
      "speaker": "原文角色名",
      "kind": "DIALOGUE",
      "full_text": "你不要逃避，告诉我真相。",
      "shot_group_ids": ["EP001-SG01"],
      "start_trigger": "角色完成具体动作并看向目标后",
      "timing_basis": "ACTUAL_READ",
      "spoken_duration_seconds": 3.2,
      "continuity_requirement": "后续片段无停顿承接，不重启呼吸和语气",
      "cross_group_exception": false,
      "cross_group_transition": null
    }
  ],
  "shot_groups": [
    {
      "shot_group_id": "EP001-SG01",
      "duration_seconds": 15,
      "duration_exception_reason": null,
      "scene_name": "金融一班教室",
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
        {"shot_id": "S01", "start_seconds": 0, "end_seconds": 3, "primary_subject": "李明与张三", "framing": "双人中景", "shot_signature": "双人中景|轴线同侧|关系建立", "purpose": "建立空间", "existence_reason": "交代出口、距离和轴线", "spoken_segments": []},
        {"shot_id": "S02", "start_seconds": 3, "end_seconds": 6, "primary_subject": "李明", "framing": "过肩中近景", "shot_signature": "过肩中近景|轴线同侧|说话者", "purpose": "说话者过肩中近景", "existence_reason": "动作触发语言并推进情绪", "spoken_segments": [{"language_id": "DIA01", "segment_index": 1, "text": "你不要逃避，", "start_mode": "ACTION_TRIGGER", "start_trigger": "角色完成具体动作并看向目标后", "spoken_duration_seconds": 1.3, "timing_basis": "ACTUAL_READ", "mouth_state": "现场口型同步", "delivery_continuity": "开始同一条完整语言"}]},
        {"shot_id": "S03", "start_seconds": 6, "end_seconds": 9, "primary_subject": "张三", "framing": "近景", "shot_signature": "近景|轴线同侧|听者反应", "purpose": "听者反应", "existence_reason": "让关系变化可见", "spoken_segments": [{"language_id": "DIA01", "segment_index": 2, "text": "告诉我", "start_mode": "CONTINUE_WITHOUT_RESTART", "start_trigger": "切到听者反应时", "spoken_duration_seconds": 0.8, "timing_basis": "ACTUAL_READ", "mouth_state": "说话者画外连续声", "delivery_continuity": "无停顿承接上一镜"}]},
        {"shot_id": "S04", "start_seconds": 9, "end_seconds": 12, "primary_subject": "李明", "framing": "近景", "shot_signature": "说话者近景|轴线同侧|语言落点", "purpose": "说话者落点", "existence_reason": "完成台词与情绪落点", "spoken_segments": [{"language_id": "DIA01", "segment_index": 3, "text": "真相。", "start_mode": "CONTINUE_WITHOUT_RESTART", "start_trigger": "切回说话者近景时", "spoken_duration_seconds": 1.1, "timing_basis": "ACTUAL_READ", "mouth_state": "现场口型连续", "delivery_continuity": "无停顿承接并完成整句"}]}
      ],
      "exit_transition": {
        "to_group_id": "EP001-SG02",
        "from_shot_signature": "说话者近景|轴线同侧|语言落点",
        "from_primary_subject": "李明",
        "from_framing": "近景",
        "to_shot_signature": "双人中景|轴线同侧|关系变化",
        "to_primary_subject": "李明与张三",
        "to_framing": "双人中景",
        "transition_method": "视线落点接双人关系镜头",
        "continuity_anchor": "李明说完后保持看向张三，张三吸气准备回答"
      },
      "prompt_asset_bindings": ["原文角色名=原文角色名音色=", "金融一班教室="],
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

`duration_planning_reason` 必须说明本集如何在用户软目标、正常90—180秒范围与剧情实际容量之间取值。低于90秒时必须填写 `duration_deviation_reason`；超过180秒始终禁止。分镜组超过项目 `preferred_max_shot_groups` 时必须填写 `shot_group_count_exception_reason`。

每镜使用 `primary_subject`、`framing` 和 `shot_signature` 固定主体、景别和完整镜头签名。每个非末组填写 `exit_transition`，并与实际前组尾镜及后组首镜完全对应；末组使用 `null`。相邻镜头签名不得相同，默认禁止 `from_primary_subject = to_primary_subject` 且前后景别均为特写。若原文或用户明确要求匹配剪辑，额外记录 `match_cut_approved=true`、`match_cut_reason` 和可见匹配依据。

所有视觉镜头都使用各自起止时间。完整对白、独白、旁白、画外音或系统语音登记在集级 `language_units` 作为原文校验基准；真正进入视频提示词的是各镜 `spoken_segments`。同一语言单元的片段按 `segment_index` 拼接后必须逐字等于 `full_text`。第一片段使用 `ACTION_TRIGGER` 并写具体动作或现场事件；后续片段使用 `CONTINUE_WITHOUT_RESTART`，无停顿承接上一镜。禁止另列独立计时音轨总设定，也禁止使用 `kind = continuous_language_block` 把整段语言伪装成一个长镜头。

语言时长优先使用 `ACTUAL_READ`；规划阶段可暂用 `ESTIMATED`，但必须依据角色声线、情绪、重音、停顿和触发动作逐段估算，生产前重新试读校时。每段 `spoken_duration_seconds` 不得超过该镜头在触发动作完成后的可用时长。

语言单元默认只属于一个分镜组。只有 `cross_group_exception=true` 且 `cross_group_transition` 同时记录上游批准、前组尾镜签名、后组首镜签名和转场方法时才允许跨组；两个镜头签名不得相同。

`prompt_asset_bindings` 是纯净提示词必须使用的等号绑定槽，不等于完整资产清单。即使不运行资产分析流程，也必须列出本组实际发声角色、出镜角色、场景、机位、道具和必要声音；这些行必须位于完整全局控制段之后、`【摄影机运动总设定】`之前。

## 导演知识调用数据

- `01_SCRIPT/director_requests/`：保存交给 `$ai-cinematic-directing-assets` 的调用请求，包括不可修改剧情事实、原文台词、完整事件、项目配置、上一组结束状态和参考版本。
- `02_SHOTGROUPS/EP001/performance_plans/`：保存人物表演资产库返回的目标、策略、听者反应、表演节拍和状态继承，不包含摄影机和最终提示词。
- `02_SHOTGROUPS/EP001/director_representations/`：保存专业库返回的中性导演镜头表示。它不是最终Seedance提示词，不包含全局固定画质段或资产等号绑定区。
- `02_SHOTGROUPS/EP001/execution_reports/`：保存镜头执行与连续性检查结果，逐镜记录第一帧、空间关系、道具手、摄影机、光线、物理和逐切点继承。
- `02_SHOTGROUPS/EP001/scene_state_ledger.json`：保存每组入组和出组的世界空间、画面空间、人物关系、人物、环境、摄影机与剧情状态。
- 分别记录 `performance_library_status`、`directing_library_status` 和 `execution_library_status`。未安装对应模块时该项为 `FALLBACK_INTERNAL`；成功调用时记录对应 Skill 名称。禁止用一个总状态掩盖某层缺失或在未调用时伪造成功。
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

`PROJECT_STATUS.json` 至少记录：当前阶段、模型配置、人物表演库状态、导演协调库状态、镜头执行库状态、导演表示版本、冻结分镜版本、状态账本版本、母资产版本、最后审核结果、待用户动作、更新时间。

任何上游版本变化使下游结果标记 `STALE`。

## 资产文件夹接入数据

- `asset_sources.json`：记录用户提供的资产文件夹绝对路径、接入时间和只读原则。
- `asset_folder_index.json`：记录扫描到的文件、相对路径、扩展名和自动匹配结果。
- `asset_review_queue.json`：逐项记录标准资产名称、候选文件、匹配状态、内容审核状态、审核证据、问题和返修建议。
- 自动扫描不得直接把资产状态改成 `READY`。只有实际内容审核通过后才能同步资产表状态。

## 校验阶段

- `planning`：配置、模型隔离、全局控制段、提示词资产绑定、每集180秒上限、分镜组时长、每个普通镜头的独立时间、语言原文片段、动作起声触发、无停顿承接、跨组限制、字幕结尾和明确命名。
- `production`：包含planning，并要求三轮审核为PASS、必须资产READY、`production_ready=true`。
- `final`：包含production，并要求真实成片时长不超过180秒、声音执行表READY、授权明确、`final_episode_ready=true`。
