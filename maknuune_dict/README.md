# Compilation of Maknuune Using LaTeX

To compile the dictionary:

1. Install TeX distribution from [here](https://www.latex-project.org/get/). *Note that the compilation cannot be done from OverLeaf because the size of the resulting PDF it is too large.*
2. Run the following script in your terminal from within this directory: 

    ```bash

    ./compile_maknuune.sh
    
    ```

    Look at the main tex file `dictionary.tex` to see all requirements in terms of images (and their paths), other tex files, etc.

3. The resulting PDF should be saved under `./dictionary.pdf`
