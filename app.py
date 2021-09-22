"""
Flask application
https://flask.palletsprojects.com/en/2.0.x/tutorial/factory/
"""

import os
import time
import json
import hashlib
import logging

from PIL import Image, ImageOps, ImageEnhance
from werkzeug.utils import secure_filename

from flask import Flask, send_file, Response, request
from jinja2 import Environment, FileSystemLoader

ALLOWED_EXTENSIONS: set = {'png', 'jpg', 'jpeg', 'gif'}

root: str = os.path.dirname(__file__)
images_path: str = os.path.join(root, 'images')
cached_path: str = os.path.join(root, 'cached')
templates_path: str = os.path.join(root, 'templates')

if not os.path.isdir(images_path):
    os.mkdir(images_path)

app: Flask = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY='dev',
    DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
)

app.logger.setLevel(logging.DEBUG)
app.config['UPLOAD_FOLDER'] = images_path

jinja: Environment = Environment(
    loader=FileSystemLoader(templates_path),
)


@app.route('/')
def hello() -> str:
    """
    Hello world example.
    """
    return 'Hello, World!'


@app.route('/images')
@app.route('/images', methods=['GET', 'POST'])
def images() -> str:
    """
    Lists uploaded images.
    """
    template: str = jinja.get_template('images.html')
    if request.method == 'POST':
        if 'file' in request.files:
            file: 'FileStorage' = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                key: set = secure_filename(file.filename)
                path: str = os.path.join(app.config['UPLOAD_FOLDER'], key)
                app.logger.debug('Upload: %s', path)
                file.save(path)
    return template.render({
        "images": [
            filename
            for dirpath, dirnames, filenames in os.walk(images_path)
            for filename in filenames
        ],
    })


@app.route('/images/<image>')
def image(image: str) -> Response:
    """
    Serves an image.
    """

    # Timing the time it takes to serve an image.
    start: float = time.time()

    # Validating the file exists in the File System.
    assert ".." not in image
    path: str = os.path.join(images_path, image)
    if not os.path.isfile(path):
        raise OSError(path)

    # Serve original file.
    if not request.args:
        elapsed: float = time.time() - start
        app.logger.debug('Original: %s, Time: %s', path, elapsed)
        return send_file(path, mimetype="image/jpg")

    # Generating a hash.
    identity: str = hashlib.md5("-".join([
        image,
        json.dumps(request.args, sort_keys=True)
    ]).encode('utf-8')).digest().hex()
    target_path: str = os.path.join(cached_path, identity) + ".jpg"

    # Processing the file.
    if not os.path.isfile(target_path):

        # Reading original image.
        image: Image = Image.open(path)

        # Altering image size.
        if request.args.get('h') and request.args.get('w'):
            new_height: int = int(request.args['h'])
            new_width: int = int(request.args['w'])
            image = image.resize((new_width, new_height))
        elif request.args.get('h'):
            original_width: int = image.size[0]
            original_height: int = image.size[1]
            new_height: int = int(request.args['h'])
            new_width: int = int(new_height * original_width / original_height)
            image = image.resize((new_width, new_height))
        elif request.args.get('w'):
            original_width: int = image.size[0]
            original_height: int = image.size[1]
            new_width: int = int(request.args['w'])
            new_height: int = int(new_width * original_height / original_width)
            image = image.resize((new_width, new_height))

        # Croping image.
        if request.args.get('format') == 'square':
            width: int = image.size[0]
            height: int = image.size[1]
            if width > height:
                top: int = 0
                bottom: int = height
                half: float = height / 2
                center: float = width / 2
                left: int = int(center - half)
                right: int = int(center + half)
                image = image.crop((left, top, right, bottom))
                app.logger.debug('Crop: %s', left, top, right, bottom)
            elif width < height:
                left: int = 0
                right: int = width
                half: float = width / 2
                center: float = height / 2
                top: int = int(center - half)
                bottom: int = int(center + half)
                image = image.crop((left, top, right, bottom))
                app.logger.debug('Crop: %s', left, top, right, bottom)

        # Rotating image.
        if request.args.get('rot'):
            angle: int = int(request.args['rot'])
            image = image.rotate(angle)

        # Flipping image.
        if request.args.get('flip') == 'h':
            image = ImageOps.mirror(image)
        elif request.args.get('flip') == 'v':
            image = ImageOps.flip(image)
        elif request.args.get('flip') == 'hv':
            image = ImageOps.flip(image)
            image = ImageOps.mirror(image)

        # Applying filters to image.
        # if request.args.get('con'):
        #     contrast: int = int(request.args['con'])
        #     enhancer: ImageEnhance = ImageEnhance.Contrast(image)
        #     image = enhancer.enhance(contrast)
        # if request.args.get('bri'):
        #     contrast: int = int(request.args['con'])
        #     enhancer: ImageEnhance = ImageEnhance.Contrast(image)
        #     image = enhancer.enhance(contrast)

        # Storing transformed image.
        # https://stackoverflow.com/questions/6788398
        image.save(
            target_path,
            "JPEG",
            quality=80,
            optimize=True,
            progressive=True
        )

    # Serving transformed image.
    elapsed: float = time.time() - start
    app.logger.debug(
        'Transformed: %s %s, Time: %s',
        request.args,
        target_path,
        elapsed
    )
    return send_file(target_path, mimetype="image/jpg")


def allowed_file(filename: set) -> bool:
    """
    Evaluates if a file is accepted.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
