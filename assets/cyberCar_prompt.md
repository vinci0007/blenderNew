先检查已完成的建模内容，下面要求继续未完成的内容

Create a production-ready futuristic hypercar model in Blender using executable VBF skills only. The project does NOT support image input, so do not reference, load, import, or analyze images at runtime. Build the model entirely from textual requirements, primitive meshes, bevels, modifiers, boolean cutouts, PBR materials, lights, camera, and keyframe animation.

Important scale requirement:
- The full car body length must be 2.7 meters from front splitter tip to rear bumper/diffuser end.
- Use real-world proportions based on length = 2.7m:
  - overall length: 2.7m
  - width: about 1.18m to 1.25m
  - height: about 0.70m to 0.78m
  - wheelbase: about 1.65m to 1.75m
  - wheel diameter: about 0.38m to 0.44m
- Keep all parts centered around world origin, with the car length along the X axis, width along Y axis, height along Z axis.
- Build the model as a unified rig hierarchy so resizing does not break the overall model:
  - create a root scale control object named Hypercar_Scale_Root at world origin
  - create a rotating turntable or rotation control under it
  - parent every car mesh, wheel, glass piece, light strip, wing, diffuser, and scene display base consistently
  - scaling should be done only by uniformly scaling Hypercar_Scale_Root
  - do not rely on non-uniform object scaling for final proportions where it would distort wheels, lights, or panel gaps
  - apply or preserve transforms so the car remains visually consistent when uniformly scaled up or down
  - keep origins and parent relationships clean

Design goal:
Create an original low, wide, mid-engine hypercar with the appearance of a technical concept-car schematic turned into a cinematic studio model. The design should resemble a compact futuristic electric hypercar with sharp aerodynamic surfaces, a very low nose, wide rear haunches, fixed rear wing, and premium hard-surface detailing.

Geometry requirements:
1) Build separate named meshes:
- main low wedge-shaped body shell
- front bumper and carbon front splitter
- hood panel with two shallow vents
- side doors with visible panel seams
- large side air intakes behind the doors
- rear fenders and rear diffuser
- fixed rear wing with two vertical supports
- windshield, side windows, and rear glass
- four wheels with black tires, multi-spoke rims, brake discs, and brake calipers
- front LED headlight housings with three small inner light points per side
- rear thin LED tail-light strips
- dark circular or rectangular display turntable

2) Shape language:
- Front: very low nose, wide central intake, aggressive narrow headlights, vertical side intake channels, carbon lower splitter.
- Side: smooth teardrop cabin, strong shoulder line, recessed door cut, large side intake, sculpted lower sill, wide rear wheel arch.
- Rear: broad haunches, fixed wing, layered diffuser fins, thin red LED tail lights.
- Use bevel modifiers and shade smooth where appropriate.
- Avoid brand logos, text labels, watermarks, or real manufacturer badges.

Color and material analysis target:
The car paint should closely match the supplied visual reference: glossy chameleon pearlescent paint with strong angle-dependent color zones. Since this project cannot use image input or image textures, simulate the look using multiple closely related PBR paint materials assigned to different panels.

Create these materials:

1) Chameleon_Main_BlueViolet_Paint
- base_color: [0.10, 0.04, 0.85, 1.0]
- metallic: 0.65
- roughness: 0.10
- clearcoat: 1.0
- clearcoat_roughness: 0.025
- Use on hood, front fenders, roof edges, and primary body panels.
- Visual target: electric blue shifting into violet.

2) Chameleon_CyanGreen_Paint
- base_color: [0.00, 0.85, 0.72, 1.0]
- metallic: 0.60
- roughness: 0.11
- clearcoat: 1.0
- Use as broad accent areas on upper doors, roof center, and shoulder highlights.
- Visual target: turquoise / emerald reflections visible across the side profile.

3) Chameleon_GoldMagenta_Paint
- base_color: [0.95, 0.62, 0.12, 1.0]
- metallic: 0.70
- roughness: 0.09
- clearcoat: 1.0
- Use subtly on rear fenders, rear deck, and selected curved side panels.
- Add small magenta/violet accent panels where possible.
- Visual target: warm gold and pink-purple highlights on curved rear surfaces.

4) Black_Carbon_Fiber
- base_color: [0.006, 0.007, 0.008, 1.0]
- metallic: 0.15
- roughness: 0.22
- clearcoat: 0.45
- Assign to front splitter, lower bumper, side skirts, side intake inserts, rear diffuser, wing supports, mirror bases, and lower door insert panels.
- If procedural weave is available, add subtle anisotropic or fine procedural dark stripe variation; otherwise use glossy black carbon-like PBR.

5) Smoked_Glass
- base_color: [0.015, 0.020, 0.025, 0.42]
- roughness: 0.02
- transmission or alpha if available
- ior: 1.45
- Assign to windshield, side windows, and rear glass.

6) Gunmetal_Wheel_Metal
- base_color: [0.16, 0.17, 0.18, 1.0]
- metallic: 1.0
- roughness: 0.23
- Assign to multi-spoke rims.

7) Matte_Black_Rubber
- base_color: [0.002, 0.002, 0.002, 1.0]
- metallic: 0.0
- roughness: 0.75
- Assign to tires.

8) Carbon_Ceramic_Brake
- base_color: [0.30, 0.29, 0.27, 1.0]
- metallic: 0.55
- roughness: 0.36
- Assign to brake discs.

9) Deep_Purple_Brake_Caliper
- base_color: [0.30, 0.015, 0.62, 1.0]
- metallic: 0.45
- roughness: 0.18
- Assign to brake calipers.

10) BluePurple_LED
- emissive color: [0.20, 0.03, 1.0, 1.0]
- emission strength: 4 to 6
- Assign to front headlights and three small LED dots per side.

11) Red_LED
- emissive color: [1.0, 0.01, 0.005, 1.0]
- emission strength: 3 to 5
- Assign to rear thin tail lights.

Scene:
- Clear the scene first.
- Add a dark futuristic studio environment: dark gray reflective floor, black-gray wall panels, cool white linear lights.
- The floor should have soft reflections to show the blue, purple, green, and gold paint.
- Add soft area lights above/front, a cool rim light from rear, and low side fill lights.
- Add a camera at low front three-quarter view, looking at the car center, focal length around 55-70mm.
- Set render engine to Cycles if available, enable denoise, use reasonable samples.

360-degree rotation animation:
- Set frame range to 1-240 and FPS to 30.
- Keep Hypercar_Scale_Root as the global scale parent.
- Animate only the rotation control / turntable object around Z axis:
  - frame 1: rotation_euler = [0, 0, 0]
  - frame 240: rotation_euler = [0, 0, 6.28318]
- Insert keyframes for rotation_euler at frame 1 and frame 240.
- Set Z rotation keyframe interpolation to LINEAR for constant speed.
- Camera remains fixed.
- The animation should loop seamlessly.
- Scaling Hypercar_Scale_Root uniformly after animation must preserve the whole car proportions, material assignment, wheel positions, lighting relationship, and rotation behavior.

Constraints:
- Do NOT use image input.
- Do NOT import image textures.
- Do NOT create non-executable pseudo skills.
- Do NOT hardcode references to objects before they are created.
- For parenting and relationships, use $ref from previous step outputs whenever possible.
- Output strictly as valid VBF skills plan JSON with executable Blender skills only.
