Create a production-ready hard-surface smartphone concept model in Blender (iPhone 17 Pro inspired), focusing ONLY on geometry and clean topology.

Requirements:
1) Build separate meshes: main chassis, camera island plate(s), camera lens rings/discs, side buttons, and front display cutout surface.
2) Chassis:
- Ultra-slim rectangular body with flat front/back planes.
- Flat machined side frame.
- Symmetric rounded corner fillets.
- Subtle edge chamfer where side frame meets front/back planes.
3) Functional cutouts:
- Left side: volume up/down + action button cutouts.
- Right side: power button cutout + larger recessed camera-control area.
- Bottom: centered USB-C cutout + symmetric grille/mic hole arrays.
4) Front:
- Center-top pill-shaped Dynamic Island cutout.
5) Rear:
- Large recessed camera island.
- Inside island: two elevated circular regions:
  - Left region: 3 large lens cutouts (two upper, one lower).
  - Right region: 1 lens + flash + lidar cutouts cluster.
- Add a subtle recessed logo on back center.
6) Mesh quality:
- Prefer all-quad where practical.
- Clean edge flow around fillets and booleans.
- Support later bevel refinement.
7) Constraints:
- Do NOT hardcode object names in relationship steps.
- For parenting/relationships, use $ref from previous step outputs.
- Ensure any referenced object is created in earlier steps.

Output strictly as valid VBF skills plan JSON with executable Blender skills only.
Do not include non-executable pseudo skills (e.g., load_skill).