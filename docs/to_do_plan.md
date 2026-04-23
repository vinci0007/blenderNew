# VBF 寤烘ā娴佺▼鏀硅繘璁″垝

**鍒涘缓鏃堕棿**: 2026-04-12
**鍒嗘瀽鏉ユ簮**: 鍩轰簬 Blender 涓撲笟寤烘ā娴佺▼鐭ヨ瘑
**鐘舵€?*: 寰呭疄鏂?
---

## 闂鎬荤粨

褰撳墠 VBF 9 闃舵寤烘ā娴佺▼瀛樺湪鐨勪笁澶ф牳蹇冮棶棰橈細

1. **闃舵瀹氫箟涓庝笓涓氭祦绋嬩笉绗?* - 鏈闈炴爣鍑嗭紝椤哄簭鍙紭鍖?2. **缂哄皯鐢ㄦ埛鍙嶉寰幆** - 褰撳墠涓?涓€娆℃€?鐢熸垚妯″紡
3. **缂哄皯鍥惧儚杈撳叆鏀寔** - 鏃犳硶鍒嗘瀽鐢ㄦ埛鎻愪緵鐨勫弬鑰冨浘

---

## 瀹炴柦璁″垝

### 瀹炴柦 A: 閲嶆瀯 Stage 娴佺▼ (P0 - 楂樹紭鍏堢骇)

**鐩爣**: 灏?9 闃舵鎵╁睍涓烘爣鍑嗕笓涓氬缓妯℃祦绋?
**棰勮宸ユ湡**: 2-4 灏忔椂

**鏂囦欢淇敼**:
- `vbf/app/client.py` - 淇敼 `stage_order` 瀹氫箟
- `vbf/llm_integration.py` - 鏇存柊 LLM Prompt schema
- `blender_provider/SKILL.md` - 鏇存柊鏂囨。

**鍏蜂綋鏀瑰姩**:

```python
# 褰撳墠 (vbf/app/client.py:126-134)
stage_order = {
    "discover": 0,
    "blockout": 1,
    "boolean": 2,
    "detail": 3,
    "bevel": 4,
    "normal_fix": 5,
    "accessories": 6,
    "material": 7,
    "finalize": 8,
}

# 閲嶆瀯涓轰笓涓氭祦绋?PROFESSIONAL_STAGE_ORDER = {
    # Phase 1: Concept
    "reference_analysis": 0,    # 鍒嗘瀽鐢ㄦ埛杈撳叆锛堝師 discover锛?    "mood_board": 1,            # NEW: 鎯呯华鏉垮垱寤?    "style_definition": 2,      # NEW: 椋庢牸纭珛
    
    # Phase 2: Blocking
    "primitive_blocking": 3,    # 绮楀潡鍒涘缓锛堝師 blockout锛?    "silhouette_validation": 4, # NEW: 杞粨楠岃瘉
    "proportion_check": 5,      # NEW: 姣斾緥纭
    
    # Phase 3: Structure
    "topology_prep": 6,         # NEW: 鎷撴墤鍑嗗
    "edge_flow": 7,             # NEW: 杈规祦鎺у埗
    "boolean_operations": 8,    # Boolean鍒囧壊锛堜繚鐣欙級
    
    # Phase 4: Detail
    "bevel_chamfer": 9,         # 鍊掕锛堝厛浜庣粏鑺傦級
    "micro_detailing": 10,      # 寰缁嗚妭锛堝師 detail锛?    "high_poly_finalize": 11,   # NEW: 楂樻ā鏈€缁堝寲
    
    # Phase 5: Polish
    "normal_baking": 12,        # 鏍囧噯鏈锛堝師 normal_fix锛?    "uv_prep": 13,              # NEW: UV鍑嗗
    "material_prep": 14,        # 鏉愯川鍑嗗锛堝師 accessories 閲嶅懡鍚嶏級
    
    # Phase 6: Finish
    "material_assignment": 15,  # 鏉愯川鍒嗛厤锛堝師 material锛?    "lighting_check": 16,       # NEW: 鐏厜棰勮
    "finalize": 17              # 鏈€缁堝鍑猴紙淇濈暀锛?}
```

**楠屾敹鏍囧噯**:
- [ ] stage_order 鏇存柊涓轰笓涓氭湳璇?- [ ] 鎵€鏈夋祴璇曢€氳繃 (tests/test_stage_system.py)
- [ ] LLM Prompt schema 鏇存柊锛?闃舵 鈫?18闃舵锛?- [ ] 鏂囨。 README.md 鏇存柊

---

### 瀹炴柦 B: 澧炲姞鐢ㄦ埛鍙嶉寰幆 (P0 - 楂樹紭鍏堢骇)

**鐩爣**: 鍦ㄥ叧閿妭鐐规彁渚涗腑閫旈瑙堝拰鐢ㄦ埛纭

**棰勮宸ユ湡**: 4-6 灏忔椂

**鏂板妯″潡**:
- `vbf/feedback_loop.py` - 鍙嶉寰幆鎺у埗鍣?- `vbf/feedback_ui.py` - 棰勮鍜屼氦浜掔晫闈?
**鍏抽敭鑺傜偣**:
```python
FEEDBACK_CHECKPOINTS = [
    ("after_silhouette", 20),      # 杞粨纭
    ("after_blocking", 35),        # 姣斾緥纭
    ("after_bevel", 60),             # 缁嗚妭绋嬪害纭
    ("before_material", 85),        # 鏈€缁堥珮妯＄‘璁?]
```

**鎺ュ彛璁捐**:
```python
class UIModelingFeedback:
    async def checkpoint(
        self,
        stage: str,
        current_progress: float,
        preview_path: str
    ) -> UserFeedback:
        """鍦ㄧ壒瀹?stage 鏆傚仠锛岀瓑寰呯敤鎴风‘璁?""
        pass
```

**楠屾敹鏍囧噯**:
- [ ] 4涓叧閿弽棣堣妭鐐瑰疄鐜?- [ ] 棰勮鎴浘鑷姩鐢熸垚
- [ ] 鐢ㄦ埛鍙€夐」锛歔缁х画, 璋冩暣, 閲嶅仛, 鍋滄]
- [ ] 涓柇鍚庡彲鎭㈠鏈哄埗

---

### 瀹炴柦 C: 闆嗘垚鍥惧儚鍒嗘瀽鑳藉姏 (P1 - 涓紭鍏堢骇)

**鐩爣**: 鏀寔鐢ㄦ埛涓婁紶鍙傝€冨浘锛孡LM 鍒嗘瀽鍚庣敓鎴愬缓妯¤鍒?
**棰勮宸ユ湡**: 3-5 灏忔椂

**鏂板妯″潡**:
- `vbf/image_analyzer.py` - 鍥惧儚鍒嗘瀽鍣?- `vbf/vlm_adapter.py` - VLM 鎺ュ叆灞?
**VLM 閫夊瀷** (鍙€?:
- GPT-4V (OpenAI)
- Claude 3 Vision (Anthropic)
- Gemini Pro Vision (Google)
- 鏈湴妯″瀷 (LLaVA 绛夛紝闇€ GPU)

**鍔熻兘瀹炵幇**:
```python
class ReferenceImageAnalyzer:
    async def analyze(self, image_path: str) -> ImageAnalysisResult:
        """鍒嗘瀽鍙傝€冨浘锛岃繑鍥炲缓妯℃寚瀵?""
        return {
            "object_type": "纭〃闈?瑙掕壊/鏈夋満",
            "dominant_shapes": ["绔嬫柟浣?, "鍦嗘煴", "鍦嗙幆"],
            "estimated_dimensions": {"height": 2.0, "width": 1.5, "depth": 1.0},
            "key_features": ["灏栭攼杈圭紭", "鍦嗚杩囨浮", "琛ㄩ潰鎸夐挳"],
            "style_hints": "鍐欏疄/椋庢牸鍖?浣庡杈瑰舰",
            "complexity_level": "绠€鍗?涓瓑/澶嶆潅"
        }
```

**CLI 鏇存柊**:
```bash
# 鏂伴€夐」
vbf --prompt "create a retro radio" --reference-image "./radio_sketch.jpg"
```

**楠屾敹鏍囧噯**:
- [ ] 鏀寔甯歌鍥剧墖鏍煎紡 (PNG/JPG/WebP)
- [ ] 鍥惧儚鍒嗘瀽缁撴灉鐢ㄤ簬鐢熸垚绗竴闃舵 plan
- [ ] CLI 鏀寔 --reference-image 鍙傛暟
- [ ] 鏂囨。鏇存柊

---

### 瀹炴柦 D: 椋庢牸妯℃澘绯荤粺 (P2 - 浣庝紭鍏堢骇)

**鐩爣**: 棰勭疆椋庢牸妯℃澘锛屽揩閫熷垏鎹㈠缓妯￠鏍?
**棰勮宸ユ湡**: 3-4 灏忔椂

**棰勭疆妯℃澘**:
```python
STYLE_TEMPLATES = {
    "hard_surface_realistic": {
        "bevel_amount": 0.02,
        "topology": "quad_only",
        "subdivision": "catmull_clark",
        "material_workflow": "pbr_metallic_roughness"
    },
    "stylized_low_poly": {
        "bevel_amount": 0,
        "topology": "triangle_friendly",
        "subdivision": "none",
        "material_workflow": "vertex_color"
    },
    "organic_character": {
        "bevel_amount": 0.1,
        "topology": "animation_ready",
        "subdivision": "catmull_clark_high",
        "material_workflow": "pbr_subsurface"
    }
}
```

**楠屾敹鏍囧噯**:
- [ ] 3绉嶄互涓婇鏍兼ā鏉?- [ ] CLI 鏀寔 --style 鍙傛暟
- [ ] 妯℃澘鍙墿灞?
---

## 瀹炴柦浼樺厛绾?
```
Phase 1 (蹇呴』): [瀹炴柦 A] + [瀹炴柦 B]
  鈹溾攢鈹€ 閲嶆瀯 stage 娴佺▼ (2-4h)
  鈹斺攢鈹€ 澧炲姞鍙嶉寰幆 (4-6h)
  鎬诲伐鏈? 6-10 灏忔椂

Phase 2 (鎺ㄨ崘): [瀹炴柦 C]
  鈹斺攢鈹€ 鍥惧儚鍒嗘瀽鑳藉姏 (3-5h)
  
Phase 3 (鍙€?: [瀹炴柦 D]
  鈹斺攢鈹€ 椋庢牸妯℃澘绯荤粺 (3-4h)

鎬诲伐鏈? 12-19 灏忔椂
```

---

## 椋庨櫓涓庝緷璧?
| 椋庨櫓 | 褰卞搷 | 缂撹В鏂规 |
|------|------|---------|
| VLM API 鎴愭湰 | 瀹炴柦 C | 鎻愪緵鏈湴妯″瀷閫夐」锛屾垨浣跨敤 cost鈥慹ffective 鐨?VLM |
| 鐢ㄦ埛鍙嶉涓柇鎭㈠ | 瀹炴柦 B | 寮哄寲 TaskState 鏈哄埗 |
| 闃舵澧炲瀵艰嚧 LLM 璁″垝杩囬暱 | 瀹炴柦 A | 浼樺寲 Prompt锛屾垨浣跨敤娓╁拰鐨勬彁绀?|

---

## 鐩稿叧鏂囦欢

- `vbf/app/client.py` - run_task() 鏍稿績娴佺▼
- `vbf/llm_integration.py` - LLM Prompt 鏋勫缓
- `vbf/task_state.py` - 鐘舵€佷繚瀛?鎭㈠
- `vbf/progress.py` - 杩涘害鏄剧ず
- `vbf/scene_state.py` - 鍦烘櫙鎹曡幏

---

**鏈€鍚庢洿鏂?*: 2026-04-12
**鐘舵€?*: 寰呯敤鎴风‘璁ゅ悗寮€濮嬪疄鏂?