## Setting Up a Virtual Environment

To ensure that all dependencies are managed properly, it is recommended to create a virtual environment for this project. Follow the steps below to set up a virtual environment:

1. **Install `virtualenv`** (if not already installed):
    ```sh
    pip install virtualenv
    ```

2. **Create a virtual environment**:
    ```sh
    virtualenv venv
    ```

3. **Activate the virtual environment**:
    - On Windows:
        ```sh
        .\venv\Scripts\activate
        ```
    - On macOS and Linux:
        ```sh
        source venv/bin/activate
        ```

4. **Install the required packages**:
    ```sh
    pip install -r requirements.txt
    ```

5. **Deactivate the virtual environment** (when done):
    ```sh
    deactivate
    ```

By following these steps, you will have a virtual environment set up with all the necessary dependencies installed.# trans-epi-script
Trans-Episode-Script is a python app that renames media files based on the closest matching transcript
