# ArcFace ONNX Model

Place the face embedding model here:

```
models/embedder_arcface.onnx
```

This file is required for enrollment (`python -m src.enroll`) and the vision node (`python -m src.vision_node --name <speaker>`).

Obtain an ArcFace / InsightFace ONNX embedder (112×112 input, L2-normalized 512-D output) from your course materials or export from your trained model. The pipeline expects:

- Input: `1×3×112×112` float32, RGB normalized as `(pixel - 127.5) / 128`
- Output: embedding vector (any dimension; typically 512)
