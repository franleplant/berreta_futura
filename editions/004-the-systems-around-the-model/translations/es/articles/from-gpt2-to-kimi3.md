---
source_id: 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

Veintidós mil quinientos ochenta. Esa es la cantidad de modelos GPT-2 de 124 millones de parámetros que caben dentro de KimiK3, con 2,8 billones de parámetros. La escala cambió en ese factor durante siete años, pero la arquitectura no se limitó a convertirse en una copia más grande.

Esta progresión sigue la presión creada por la longitud de secuencia, el ancho de banda de memoria, el estado recurrente, la recuperación selectiva y la capacidad dispersa.

## GPT-2 y la caché

GPT-2 es un transformer de solo decodificador. Los embeddings de tokens y posiciones ingresan en una pila de bloques. Cada bloque aplica autoatención causal y un MLP mediante conexiones residuales. Una normalización final y una cabeza de modelo de lenguaje producen logits para el vocabulario.

Durante la generación autorregresiva, solo los logits de la última posición seleccionan el siguiente token. Sin caché, cada token nuevo obligaría al modelo a volver a calcular las proyecciones para toda la secuencia precedente.

La caché KV guarda las claves y los valores de los tokens anteriores. Elimina cómputo redundante, pero crece con la longitud de secuencia y puede convertirse en un cuello de botella para el ancho de banda de memoria. La atención softmax completa también compara cada consulta con cada clave, por lo que los contextos largos siguen siendo costosos aunque la generación use caché.

## De la atención lineal a DeltaNet

La atención softmax aplica su no linealidad después del producto entre consulta y clave. La atención lineal aplica un mapa de características por separado a consultas y claves, lo que permite reasociar el cómputo. En vez de conservar cada par clave-valor, el modelo puede condensar el historial en un estado de tamaño fijo.

Esto cambia el comportamiento de escalado, pero también comprime información. Varias claves escriben en el mismo estado. Las representaciones similares interfieren entre sí y el mapa de características es menos expresivo que la atención softmax completa.

DeltaNet trata el estado como pesos rápidos y aplica una regla delta. Antes de escribir una nueva asociación clave-valor, estima qué recuperaría el estado actual para esa clave. La actualización almacena la diferencia entre el valor deseado y la predicción existente.

La corrección reduce la interferencia. No hace que la recurrencia sea gratuita. El prefill todavía tiene una estructura secuencial y una implementación útil debe recuperar trabajo paralelo.

Las formulaciones por bloques ofrecen el puente. Un bloque puede calcular trabajo convencional, similar a la atención, dentro de sí mismo y transportar un estado recurrente entre bloques. Un tamaño de bloque de uno se parece a la recurrencia pura. Un bloque tan grande como la secuencia se aproxima a la atención cuadrática completa. Los tamaños intermedios intercambian capacidad local entre pares por un estado recurrente acotado.

## Gated DeltaNet

Un estado recurrente puramente aditivo nunca olvida. Una compuerta permite que el modelo atenúe la información antigua antes de aplicar la actualización delta.

Gated DeltaNet combina una recurrencia con compuertas al estilo Mamba y la regla delta. La compuerta decide cuánto estado sobrevive. La corrección delta decide cómo una asociación nueva debe reemplazar lo que el estado predice en ese momento.

Esto es más que una optimización. Una memoria de tamaño fijo debe elegir qué conservar y qué sobrescribir. Las compuertas permiten aprender esa elección.

## Kimi Linear

Kimi Linear se apoya en Gated DeltaNet mediante Kimi Delta Attention y compuertas más detalladas. Es una arquitectura híbrida, no la declaración de que un único mecanismo reemplaza a todos los demás.

El diseño intercala capas recurrentes KDA con capas periódicas de Multi-head Latent Attention. KDA aporta memoria recurrente de estado constante. MLA puede recuperar información selectivamente del contexto de tokens cuando el estado comprimido no es suficiente.

La arquitectura también reemplaza los bloques MLP densos con capas Mixture-of-Experts. El enrutamiento disperso aumenta la capacidad de parámetros sin activar todos los parámetros para cada token. Proyecciones adicionales amplían la capacidad de la ruta delta.

El cambio importante es la división del trabajo. El estado recurrente se ocupa de una memoria continua y barata. La atención periódica realiza lecturas selectivas de un contexto más completo. Los expertos aportan cómputo condicional.

## KimiK3

KimiK3 conserva la forma híbrida. Tres de cada cuatro capas de atención usan Kimi Delta Attention, mientras que la cuarta usa Multi-head Latent Attention. Su capacidad de feed-forward proviene de un gran sistema Mixture-of-Experts.

El modelo tiene 898 expertos en total. Dos son compartidos, mientras que el router selecciona entre los expertos restantes para cada token. Los expertos operan en un espacio latente comprimido, lo que reduce el costo de la capacidad dispersa.

Gated MLA controla cuánto de cada característica recuperada pasa al flujo residual. La compresión de consultas de MLA y las compuertas de salida reducen el costo y regulan lo que aporta la capa de atención.

KimiK3 también usa residuos de atención por bloques. Un transformer convencional transporta un solo flujo residual a través de cada capa. Aquí, los bloques pueden recuperar resultados acumulados de atención y MLP a lo largo de un grupo de capas. El modelo obtiene acceso selectivo en profundidad sin pagar por ese mecanismo en cada capa.

Los mecanismos de recurrencia y profundidad abordan pérdidas relacionadas. KDA comprime el historial de la secuencia en un estado fijo y debe descartar información. MLA puede recuperarla del contexto de tokens. El acceso residual por bloques permite que las capas posteriores recuperen información seleccionada del cómputo anterior.

## Qué cambió

La progresión de GPT-2 a KimiK3 no es un reemplazo directo de la atención.

La caché KV evita recalcular el pasado, pero conserva una memoria creciente. La atención lineal comprime el pasado en un estado fijo, pero pierde precisión expresiva. DeltaNet corrige las escrituras para reducir la interferencia. Las compuertas aprenden qué olvidar. KDA hace esas actualizaciones más selectivas. MLA periódica recupera el acceso al contexto completo. Los expertos dispersos agregan capacidad condicional. El acceso residual por bloques agrega memoria selectiva a través de la profundidad.

KimiK3 combina memoria recurrente de estado constante, recuperación periódica mediante softmax, capacidad dispersa de expertos y acceso selectivo entre capas. El modelo es enormemente más grande que GPT-2, pero la historia más interesante es cómo sus componentes dividen el trabajo que antes intentaba realizar un único bloque transformer uniforme.
