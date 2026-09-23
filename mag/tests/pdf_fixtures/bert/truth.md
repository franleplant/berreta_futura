We introduce a new language representa-tion model called BERT, which stands for Bidirectional Encoder Representations from Transformers.

As a re-sult, the pre-trained BERT model can be fine-tuned with just one additional output layer to create state-of-the-art models for a wide range of tasks, such as question answering and language inference, without substantial task-specific architecture modifications.

where models are required to produce fine-grained output at the token level (Tjong Kim Sang and De Meulder, 2003; Rajpurkar et al., 2016).

There are two existing strategies for apply-ing pre-trained language representations to down-stream tasks: feature-based and fine-tuning.

For example, in OpenAI GPT, the authors use a left-to-right architecture, where every token can only at-tend to previous tokens in the self-attention layers of the Transformer (Vaswani et al., 2017).

The masked language model randomly masks some of the tokens from the input, and the objective is to predict the original vocabulary id of the masked

Figure 2: BERT input representation. The input embeddings are the sum of the token embeddings, the segmenta-tion embeddings and the position embeddings.

The NSP task is closely related to representation-learning objectives used in Jernite et al. (2017) and Logeswaran and Lee (2018).

Fine-tuning is straightforward since the self-attention mechanism in the Transformer al-lows BERT to model many downstream tasks—whether they involve single text or text pairs—by swapping out the appropriate inputs and outputs.

(3) question-passage pairs in question answering, and (4) a degenerate text-∅ pair in text classification or sequence tagging.

The General Language Understanding Evaluation (GLUE) benchmark (Wang et al., 2018a) is a col-lection of diverse natural language understanding tasks.

For example, the BERT SQuAD model can be trained in around 30 minutes on a single Cloud TPU to achieve a Dev F1 score of 91.0%.
