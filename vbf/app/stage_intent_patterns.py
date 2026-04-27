from __future__ import annotations

from typing import Tuple


NEGATED_GEOMETRY_ONLY_PATTERNS: Tuple[str, ...] = (
    r"\bdo\s+not\s+only\s+(?:create|build|make|model)",
    r"\bdon't\s+only\s+(?:create|build|make|model)",
    r"\bnot\s+only\s+(?:create|build|make|model|geometry)",
)

GEOMETRY_ONLY_PATTERNS: Tuple[str, ...] = (
    r"\bonly\s+(?:create|build|make)\s+(?:the\s+)?(?:model|mesh|geometry)\b",
    r"\b(?:create|build|make)\s+only\s+(?:the\s+)?(?:model|mesh|geometry)\b",
    r"\b(?:geometry|model|mesh)\s+only\b",
    r"\bonly\s+(?:on\s+)?geometry\b",
    r"\bfocus(?:ing)?\s+only\s+on\s+geometry\b",
    r"\bonly\s+model(?:ing)?\b",
    r"\u53ea\u5efa\u6a21",
    r"\u4ec5\u5efa\u6a21",
    r"\u53ea\u505a(?:\u6a21\u578b|\u51e0\u4f55)",
    r"\u4ec5\u505a(?:\u6a21\u578b|\u51e0\u4f55)",
)

NO_UV_PATTERNS: Tuple[str, ...] = (
    r"\b(?:no|without)\s+(?:uv|unwrap(?:ping)?|texture(?:s)?|material(?:s)?|pbr)\b",
    r"\b(?:no|without)\s+material(?:s)?\s+or\s+(?:final\s+)?render(?:ing)?\b",
    r"\b(?:no|without)\s+textur(?:e|ing)\b",
    r"\bdo\s+not\s+(?:add|create|use)\s+(?:uv|texture(?:s)?|material(?:s)?|pbr)\b",
    r"\bexclude\s+(?:uv|texture(?:s)?|material(?:s)?|pbr)\b",
    r"\u4e0d\u8981(?:\u7eb9\u7406|\u6750\u8d28)",
    r"\u4e0d\u8981[^閿?閵嗕繑*(?:\u7eb9\u7406|\u6750\u8d28)",
)

NO_LIGHTING_PATTERNS: Tuple[str, ...] = (
    r"\b(?:no|without)\s+(?:lighting|lights?|environment\s+lighting|studio\s+lighting)\b",
    r"\b(?:no|without)\s+(?:textur(?:e|ing)|materials?),\s*lighting\b",
    r"\bdo\s+not\s+(?:add|create|set\s+up|use)\s+(?:lighting|lights?)\b",
    r"\bexclude\s+(?:lighting|lights?)\b",
    r"\u4e0d\u8981(?:\u706f\u5149|\u73af\u5883\u5149)",
)

NO_ANIMATION_PATTERNS: Tuple[str, ...] = (
    r"\b(?:no|without)\s+(?:animation|animating|keyframes?|motion)\b",
    r"\bdo\s+not\s+(?:animate|add\s+animation|keyframe)\b",
    r"\bexclude\s+(?:animation|keyframes?|motion)\b",
    r"\u4e0d\u8981(?:\u52a8\u753b|\u5173\u952e\u5e27)",
)

NO_RENDER_PATTERNS: Tuple[str, ...] = (
    r"\b(?:no|without)\s+(?:final\s+)?(?:render|rendering|camera\s+render|shot|image)\b",
    r"\b(?:no|without)\s+animation\s+or\s+(?:final\s+)?render\b",
    r"\b(?:no|without)\s+(?:materials?|textures?|lighting|lights?|animation)\s+or\s+(?:final\s+)?render(?:ing)?\b",
    r"\b(?:no|without)\s+(?:textur(?:e|ing)|materials?|lighting|lights?),\s*(?:lighting|lights?|animation),?\s+or\s+(?:final\s+)?render(?:ing)?\b",
    r"\bdo\s+not\s+(?:render|create\s+a\s+shot|output\s+an\s+image)\b",
    r"\bexclude\s+(?:render|rendering|camera|shot|image)\b",
    r"\u4e0d\u8981(?:\u6e32\u67d3|\u51fa\u56fe|\u955c\u5934)",
    r"\u4e0d\u8981[^閿?閵嗕繑*\u6e32\u67d3",
)

UV_DIRECT_PATTERNS: Tuple[str, ...] = (
    r"\buv\b",
    r"\bunwrap(?:ping)?\b",
    r"\btexture(?:s|d|ing)?\b",
    r"\bmaterial(?:s)?\b",
    r"\bpbr\b",
    r"\balbedo\b",
    r"\broughness\b",
    r"\bmetal(?:ness|lic)?\b",
    r"\u7eb9\u7406",
    r"\u6750\u8d28",
)

LIGHTING_DIRECT_PATTERNS: Tuple[str, ...] = (
    r"\blighting\b",
    r"\blight\s+(?:setup|rig|the\s+scene)\b",
    r"\benvironment\s+(?:lighting|light|setup|world|scene)\b",
    r"\bworld\s+(?:lighting|environment|background)\b",
    r"\bhdr[i]?\b",
    r"\bstudio\s+light(?:ing)?\b",
    r"\u706f\u5149",
    r"\u73af\u5883\u5149",
    r"\u573a\u666f\u5149",
)

ANIMATION_DIRECT_PATTERNS: Tuple[str, ...] = (
    r"\banimat(?:e|ed|ion|ing)\b",
    r"\bkeyframe(?:s|d)?\b",
    r"\bmotion\b",
    r"\bfall(?:ing)?\b",
    r"\bdrop(?:ping|ped)?\b",
    r"\bturntable\b",
    r"\u52a8\u753b",
    r"\u5173\u952e\u5e27",
    r"\u5760\u843d",
)

RENDER_DIRECT_PATTERNS: Tuple[str, ...] = (
    r"\brender(?:ed|ing)?\b",
    r"\bcinematic\b",
    r"\bfilm(?:ic)?\b",
    r"\bproduct\s+shot\b",
    r"\bfinal\s+shot\b",
    r"\bhero\s+shot\b",
    r"\bbeauty\s+shot\b",
    r"\bfinal\s+image\b",
    r"\bpreview\s+image\b",
    r"\u6e32\u67d3",
    r"\u51fa\u56fe",
    r"\u955c\u5934",
    r"\u5f71\u89c6",
)

CAMERA_DIRECT_PATTERNS: Tuple[str, ...] = (
    r"\bscene\s+camera\b",
    r"\bcamera\s+(?:view|setup|render|angle|shot|path|tracking)\b",
    r"\bcreate\s+(?:a\s+)?camera\b",
    r"\bset\s+(?:up\s+)?(?:the\s+)?camera\b",
    r"\u6444\u50cf\u673a\u89c6\u89d2",
    r"\u76f8\u673a\u89c6\u89d2",
)

MATERIAL_DELIVERABLE_PATTERNS: Tuple[str, ...] = (
    r"\brealistic\b",
    r"\bphotoreal(?:istic|ism)?\b",
    r"\bphoto[-\s]?real(?:istic)?\b",
    r"\bphysically\s+based\b",
    r"\bgame[-\s]?ready\b",
    r"\btextured\s+asset\b",
    r"\bproduction[-\s]?ready\s+(?:asset|prop|object)\b",
    r"\u5199\u5b9e",
    r"\u7269\u7406\u771f\u5b9e",
)

PRESENTATION_DELIVERABLE_PATTERNS: Tuple[str, ...] = (
    r"\brender[-\s]?ready\b",
    r"\bpresentation[-\s]?ready\b",
    r"\bshowcase\b",
    r"\bmarketing\b",
    r"\badvertis(?:ing|ement)\b",
    r"\bproduct\s+visual(?:ization)?\b",
    r"\bfinal\s+(?:result|deliverable|visual|presentation)\b",
    r"\bcomplete\s+(?:scene|presentation|visual)\b",
    r"\bfinished\s+(?:scene|visual|presentation)\b",
    r"\bbeauty\s+render\b",
    r"\u5199\u5b9e",
    r"\u5c55\u793a",
    r"\u5b8c\u6574\u573a\u666f",
    r"\u6700\u7ec8\u6548\u679c",
)

CONTRAST_SCOPE_PATTERNS: Tuple[str, ...] = (
    r"\b(?:but|however|although|despite)\b",
    r"\b\u4f46(?:\u662f)?\b",
    r"\b\u4e0d\u8fc7\b",
)

BROAD_REQUEST_PATTERNS: Tuple[str, ...] = (
    r"\b(?:complete|full|finished|final|polished|professional)\b",
    r"\b(?:beautiful|impressive|high\s+quality)\b",
    r"\u5b8c\u6574",
    r"\u6700\u7ec8",
    r"\u9ad8\u8d28\u91cf",
)
