# TML-d24-varloop-research Model Card

Thinking Machines Lab, Inc. · Nov 20, 2026

## 1. General information

### Model name

TML-d24-varloop-research

### Legal name of the model provider

Thinking Machines Lab, Inc.

### Date of release

Nov 20, 2026

### License

Apache 2.0

### Intended uses

TML-d24-varloop-research is a multimodal research model that accepts text and image inputs and generates text outputs. It is a variable-looped counterpart to Inkling 2 Mini: whereas Inkling 2 Mini always runs its looped layers a fixed number of times, the number of loops in this model can be chosen at inference time. We are releasing it with open weights to support research on looped models. Because the number of loops can be varied on a single set of weights, the model allows cleaner comparisons of how additional looped computation affects a model’s internal computation and overall capabilities.

[Model Acceptable Use Policy](https://thinkingmachines.ai/model-acceptable-use-policy/)

### Languages

English, general multilingual support

## 2. Model properties

### Model type

Multimodal autoregressive looped transformer

### Architecture type

A 24-layer decoder-only transformer with sparse Mixture-of-Experts (MoE) feed-forward layers. The middle 12 layers run a variable number of times with shared weights, chosen at inference time; the model was trained with 1 to 5 passes. In each layer, each token is routed to 8 of 128 experts. Attention is a hybrid of local and global layers. The model is natively multimodal – images are encoded via a vision transformer – with image and text inputs projected into a shared hidden space and processed jointly by the decoder.

### Parameters

26.4B, 3.4B active

Note: each extra pass through the looped layers adds about 1.0B effective active parameters per token. This corresponds to 3.4B active parameters at 1 pass, 5.4B at 3 passes, and 7.4B at 5 passes.

### Numerics support

NVFP4 and MXFP8

### Input modalities

- Text: UTF-8 encoded text
- Image: Any pixel-based image input. For optimal performance, each image dimension should be between 40px to 4096px.

TML-d24-varloop-research supports a context window of up to 1M tokens.

### Output modalities

Text

## 3. Methods of distribution

The weights are available for download through Hugging Face [here](https://huggingface.co/thinkingmachines/tml-d24-varloop-research).

### API access to the model

The model is not available through an API, including Tinker. It is distributed as open weights only.

### Running the open weights model on your own system

#### Required hardware

The model is distributed as a single checkpoint of about 20GB. Its expert layers are NVFP4, the last four use MXFP8, and the remaining weights are BF16.

The checkpoint requires a single machine with at least 32GB of GPU or unified memory. This can be met with any of the following example configurations:

- 1x NVIDIA DGX Spark
- 1x NVIDIA GPU with 32GB or more of VRAM (for example, GeForce RTX 5090 or RTX PRO 6000 Blackwell)
- Apple silicon Mac with 32GB or more of unified memory (for example, Mac mini)

The model uses the same mixed NVFP4 and MXFP8 precision it was trained in, so this checkpoint is its native precision and needs no further quantization.

#### Required software

Running the model directly on your own hardware requires an inference deployment framework:

- For macOS: Ollama, Exo Labs
- For NVIDIA: SGLang, vLLM, Unsloth, Hugging Face, along with all of their respective dependency libraries.

## 4. Training

### Data types

Training data includes a broad variety of content types, including text, images, video.

### Data provenance

Training data for the model was drawn from publicly available sources, acquired from third-parties, generated internally, or synthetically generated or augmented. Publicly available data includes content from the public internet and publicly accessible repositories.

### Curation methodologies

Data curation includes cleaning, processing, and modifying datasets. These processing steps, which vary by data type, may include deduplication and filtering to remove junk or other low-quality data, or to advance safety or other objectives.

### Training with variable looping

TML-d24-varloop-research shares its pretraining and first stage of midtraining with Inkling 2 Mini. For the rest of midtraining, it was trained with 1 to 5 passes through the looped layers, sampled in a 1:2:6:2:1 ratio, and it was then post-trained with 3 passes. Because 3 passes dominated training once looping was introduced, performance at other pass counts may understate what models trained specifically at those counts could achieve. The two models’ later training stages differ, so we caution against comparing TML-d24-varloop-research directly to Inkling 2 Mini.

## 5. Evaluations

Each chart shows one benchmark score for TML-d24-varloop-research run at 1 to 5 passes through its looped layers, beside Inkling 2 Mini, which always runs 3 passes.

### Agentic Coding

### Agentic Search, Tool Use, and Knowledge Work

### Vision Interpretation and Creation

### Reasoning, Knowledge, and Epistemics

### Safety and Alignment

## 6. Safety

We evaluated this model with the same pre-release process as Inkling 2 Mini. It is less capable than models whose weights we have already released on CBRN and cyber evaluations, and it refuses harmful requests about as reliably as Inkling 2 Small.

For production use, we recommend Inkling 2 Mini as it generally performs better on capabilities and alignment evaluations. We do not intend TML-d24-varloop-research for production use.

Across all areas, we concluded that TML-d24-varloop-research did not present risk of material uplift beyond what’s already available in the open-weight ecosystem.

## 7. Bias, risks and limitations

TML-d24-varloop-research is a research model, not a production model. It may exhibit general limitations common to foundation models, including hallucination (generating plausible but factually incorrect or unsupported content), occasional failures to follow instructions precisely, and degraded performance in long multi-turn conversations. As with other large-scale models trained on web-derived and synthetic data, TML-d24-varloop-research may reflect biases present in its training data, including demographic, cultural, or linguistic biases, and may perform unevenly across languages, dialects, or subject domains that were less represented during training.

TML-d24-varloop-research’s knowledge is limited to information available as of its training cutoff, and it may not reflect events, developments, or changes that occurred afterward.

TML-d24-varloop-research is intended to be a research artifact. It has not been carefully tuned for deployment, and may behave unpredictably at pass counts other than 3. We do not recommend deploying this model in production or user-facing applications.

## 8. Legal

[Training Data Documentation](https://thinkingmachines.ai/training-data-documentation/)
