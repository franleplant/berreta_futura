Adam Paszke University of Warsaw adam.paszke@gmail.com

Andreas Köpf Xamla andreas.koepf@xamla.com

Deep learning frameworks have often focused on either usability or speed, but not both.

PyTorch is a machine learning library that shows that these two goals are in fact compatible: it provides an imperative and Pythonic programming style that supports code as a model, makes debugging easy and is consistent with other popular scientific computing libraries, while remaining efficient and supporting hardware accelerators such as GPUs.

We demonstrate the efficiency of individual subsystems, as well as the overall speed of PyTorch on several common benchmarks.

Note that linear layers are of course part of the library, but we show an example implementation to highlight how simple it is.

```python
class LinearLayer(Module):
   def __init__(self, in_sz, out_sz):
      super().__init__()
      t1 = torch.randn(in_sz, out_sz)
      self.w = nn.Parameter(t1)
      t2 = torch.randn(out_sz)
      self.b = nn.Parameter(t2)

   def forward(self, activations):
      t = torch.mm(activations, self.w)
      return t + self.b
```

```python
class FullBasicModel(nn.Module):
   def __init__(self):
      super().__init__()
      self.conv = nn.Conv2d(1, 128, 3)
      self.fc = LinearLayer(128, 10)

   def forward(self, x):
      t1 = self.conv(x)
      t2 = nn.functional.relu(t1)
      t3 = self.fc(t1)
      return nn.functional.softmax(t3)
```

Listing 1: A custom layer used as a building block for a simple but complete neural network.

in PyTorch easily adapts to this setting as shown in Listing 2.

```python
discriminator = create_discriminator()
generator = create_generator()
optimD = optim.Adam(discriminator.parameters())
optimG = optim.Adam(generator.parameters())

def step(real_sample):
  # (1) Update Discriminator
  errD_real = loss(discriminator(real_sample), real_label)
  errD_real.backward()
  fake = generator(get_noise())
  errD_fake = loss(discriminator(fake.detach(), fake_label)
  errD_fake.backward()
  optimD.step()
  # (2) Update Generator
  errG = loss(discriminator(fake), real_label)
  errG.backward()
  optimG.step()
```

Listing 2: Simplified training of a generative adversarial networks.

Since PyTorch programs execute eagerly, all the features of Python are available throughout the whole design process.

Easy and efficient interoperability is one of the top priorities for PyTorch because it opens the possibility to leverage the rich ecosystem of Python libraries as part of user programs.

and backward() methods, which specify the function and its derivative (or more formally the vector-Jacobian product).

Differentiating functions with more outputs than inputs is more efficiently executed using forward-mode automatic differentiation, but this use case is less common for machine learning applications.

In fact, Torch7 utilized the garbage collector built into Lua, and a common anti-pattern among the users was to sprinkle the program with explicit triggers to the garbage collector,

and __len__ (the length op-erator), making datasets behave like (possibly lazy) lists.

The one-pool-per-stream design assumption simplifies the implementation and improves the perfor-mance of the allocator: because the CPU runs ahead of the GPU, memory is freed on the CPU before

Finally, we can get an overall sense of single-machine eager mode performance of PyTorch by com-paring it to three popular graph-based deep learning frameworks (CNTK, MXNet and TensorFlow),
