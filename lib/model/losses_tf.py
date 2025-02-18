#!/usr/bin/env python3
""" Custom Loss Functions for faceswap.py """

from __future__ import absolute_import

import logging
from typing import Tuple

import numpy as np
import tensorflow as tf

# Ignore linting errors from Tensorflow's thoroughly broken import system
from tensorflow.python.keras.engine import compile_utils  # noqa pylint:disable=no-name-in-module,import-error
from tensorflow.keras import backend as K  # pylint:disable=import-error

logger = logging.getLogger(__name__)


class DSSIMObjective(tf.keras.losses.Loss):  # pylint:disable=too-few-public-methods
    """ DSSIM Loss Function

    Difference of Structural Similarity (DSSIM loss function).

    Parameters
    ----------
    k_1: float, optional
        Parameter of the SSIM. Default: `0.01`
    k_2: float, optional
        Parameter of the SSIM. Default: `0.03`
    filter_size: int, optional
        size of gaussian filter Default: `11`
    filter_sigma: float, optional
        Width of gaussian filter Default: `1.5`
    max_value: float, optional
        Max value of the output. Default: `1.0`

    Notes
    ------
    You should add a regularization term like a l2 loss in addition to this one.
    """
    def __init__(self, k_1=0.01, k_2=0.03, filter_size=11, filter_sigma=1.5, max_value=1.0):
        super().__init__(name="DSSIMObjective", reduction=tf.keras.losses.Reduction.NONE)
        self._filter_size = filter_size
        self._filter_sigma = filter_sigma
        self._k_1 = k_1
        self._k_2 = k_2
        self._max_value = max_value

    def call(self, y_true, y_pred):
        """ Call the DSSIM Loss Function.

        Parameters
        ----------
        y_true: tensor or variable
            The ground truth value
        y_pred: tensor or variable
            The predicted value

        Returns
        -------
        tensor
            The DSSIM Loss value
        """
        ssim = tf.image.ssim(y_true,
                             y_pred,
                             self._max_value,
                             filter_size=self._filter_size,
                             filter_sigma=self._filter_sigma,
                             k1=self._k_1,
                             k2=self._k_2)
        dssim_loss = (1. - ssim) / 2.0
        return dssim_loss


class MSSSIMLoss(tf.keras.losses.Loss):  # pylint:disable=too-few-public-methods
    """ Multiscale Structural Similarity Loss Function

    Parameters
    ----------
    k_1: float, optional
        Parameter of the SSIM. Default: `0.01`
    k_2: float, optional
        Parameter of the SSIM. Default: `0.03`
    filter_size: int, optional
        size of gaussian filter Default: `11`
    filter_sigma: float, optional
        Width of gaussian filter Default: `1.5`
    max_value: float, optional
        Max value of the output. Default: `1.0`
    power_factors: tuple, optional
        Iterable of weights for each of the scales. The number of scales used is the length of the
        list. Index 0 is the unscaled resolution's weight and each increasing scale corresponds to
        the image being downsampled by 2. Defaults to the values obtained in the original paper.
        Default: (0.0448, 0.2856, 0.3001, 0.2363, 0.1333)

    Notes
    ------
    You should add a regularization term like a l2 loss in addition to this one.
    """
    def __init__(self,
                 k_1=0.01,
                 k_2=0.03,
                 filter_size=4,
                 filter_sigma=1.5,
                 max_value=1.0,
                 power_factors=(0.0448, 0.2856, 0.3001, 0.2363, 0.1333)):
        super().__init__(name="SSIM_Multiscale_Loss", reduction=tf.keras.losses.Reduction.NONE)
        self.filter_size = filter_size
        self.filter_sigma = filter_sigma
        self.k_1 = k_1
        self.k_2 = k_2
        self.max_value = max_value
        self.power_factors = power_factors

    def call(self, y_true, y_pred):
        """ Call the MS-SSIM Loss Function.

        Parameters
        ----------
        y_true: tensor or variable
            The ground truth value
        y_pred: tensor or variable
            The predicted value

        Returns
        -------
        tensor
            The MS-SSIM Loss value
        """
        im_size = K.int_shape(y_true)[1]
        # filter size cannot be larger than the smallest scale
        smallest_scale = self._get_smallest_size(im_size, len(self.power_factors) - 1)
        filter_size = min(self.filter_size, smallest_scale)

        ms_ssim = tf.image.ssim_multiscale(y_true,
                                           y_pred,
                                           self.max_value,
                                           power_factors=self.power_factors,
                                           filter_size=filter_size,
                                           filter_sigma=self.filter_sigma,
                                           k1=self.k_1,
                                           k2=self.k_2)
        ms_ssim_loss = 1. - ms_ssim
        return ms_ssim_loss

    def _get_smallest_size(self, size, idx):
        """ Recursive function to obtain the smallest size that the image will be scaled to.

        Parameters
        ----------
        size: int
            The current scaled size to iterate through
        idx: int
            The current iteration to be performed. When iteration hits zero the value will
            be returned

        Returns
        -------
        int
            The smallest size the image will be scaled to based on the original image size and
            the amount of scaling factors that will occur
        """
        logger.debug("scale id: %s, size: %s", idx, size)
        if idx > 0:
            size = self._get_smallest_size(size // 2, idx - 1)
        return size


class GeneralizedLoss(tf.keras.losses.Loss):  # pylint:disable=too-few-public-methods
    """  Generalized function used to return a large variety of mathematical loss functions.

    The primary benefit is a smooth, differentiable version of L1 loss.

    References
    ----------
    Barron, J. A More General Robust Loss Function - https://arxiv.org/pdf/1701.03077.pdf

    Example
    -------
    >>> a=1.0, x>>c , c=1.0/255.0  # will give a smoothly differentiable version of L1 / MAE loss
    >>> a=1.999999 (limit as a->2), beta=1.0/255.0 # will give L2 / RMSE loss

    Parameters
    ----------
    alpha: float, optional
        Penalty factor. Larger number give larger weight to large deviations. Default: `1.0`
    beta: float, optional
        Scale factor used to adjust to the input scale (i.e. inputs of mean `1e-4` or `256`).
        Default: `1.0/255.0`
    """
    def __init__(self, alpha=1.0, beta=1.0/255.0):
        super().__init__(name="generalized_loss")
        self.alpha = alpha
        self.beta = beta

    def call(self, y_true, y_pred):
        """ Call the Generalized Loss Function

        Parameters
        ----------
        y_true: tensor or variable
            The ground truth value
        y_pred: tensor or variable
            The predicted value

        Returns
        -------
        tensor
            The loss value from the results of function(y_pred - y_true)
        """
        diff = y_pred - y_true
        second = (K.pow(K.pow(diff/self.beta, 2.) / K.abs(2. - self.alpha) + 1.,
                        (self.alpha / 2.)) - 1.)
        loss = (K.abs(2. - self.alpha)/self.alpha) * second
        loss = K.mean(loss, axis=-1) * self.beta
        return loss


class LInfNorm(tf.keras.losses.Loss):  # pylint:disable=too-few-public-methods
    """ Calculate the L-inf norm as a loss function. """
    def __init__(self):
        super().__init__(name="l_inf_norm_loss")

    @classmethod
    def call(cls, y_true, y_pred):
        """ Call the L-inf norm loss function.

        Parameters
        ----------
        y_true: tensor or variable
            The ground truth value
        y_pred: tensor or variable
            The predicted value

        Returns
        -------
        tensor
            The loss value
        """
        diff = K.abs(y_true - y_pred)
        max_loss = K.max(diff, axis=(1, 2), keepdims=True)
        loss = K.mean(max_loss, axis=-1)
        return loss


class GradientLoss(tf.keras.losses.Loss):  # pylint:disable=too-few-public-methods
    """ Gradient Loss Function.

    Calculates the first and second order gradient difference between pixels of an image in the x
    and y dimensions. These gradients are then compared between the ground truth and the predicted
    image and the difference is taken. When used as a loss, its minimization will result in
    predicted images approaching the same level of sharpness / blurriness as the ground truth.

    References
    ----------
    TV+TV2 Regularization with Non-Convex Sparseness-Inducing Penalty for Image Restoration,
    Chengwu Lu & Hua Huang, 2014 - http://downloads.hindawi.com/journals/mpe/2014/790547.pdf
    """
    def __init__(self):
        super().__init__(name="generalized_loss")
        self.generalized_loss = GeneralizedLoss(alpha=1.9999)

    def call(self, y_true, y_pred):
        """ Call the gradient loss function.

        Parameters
        ----------
        y_true: tensor or variable
            The ground truth value
        y_pred: tensor or variable
            The predicted value

        Returns
        -------
        tensor
            The loss value
        """
        tv_weight = 1.0
        tv2_weight = 1.0
        loss = 0.0
        loss += tv_weight * (self.generalized_loss(self._diff_x(y_true), self._diff_x(y_pred)) +
                             self.generalized_loss(self._diff_y(y_true), self._diff_y(y_pred)))
        loss += tv2_weight * (self.generalized_loss(self._diff_xx(y_true), self._diff_xx(y_pred)) +
                              self.generalized_loss(self._diff_yy(y_true), self._diff_yy(y_pred)) +
                              self.generalized_loss(self._diff_xy(y_true), self._diff_xy(y_pred))
                              * 2.)
        loss = loss / (tv_weight + tv2_weight)
        # TODO simplify to use MSE instead
        return loss

    @classmethod
    def _diff_x(cls, img):
        """ X Difference """
        x_left = img[:, :, 1:2, :] - img[:, :, 0:1, :]
        x_inner = img[:, :, 2:, :] - img[:, :, :-2, :]
        x_right = img[:, :, -1:, :] - img[:, :, -2:-1, :]
        x_out = K.concatenate([x_left, x_inner, x_right], axis=2)
        return x_out * 0.5

    @classmethod
    def _diff_y(cls, img):
        """ Y Difference """
        y_top = img[:, 1:2, :, :] - img[:, 0:1, :, :]
        y_inner = img[:, 2:, :, :] - img[:, :-2, :, :]
        y_bot = img[:, -1:, :, :] - img[:, -2:-1, :, :]
        y_out = K.concatenate([y_top, y_inner, y_bot], axis=1)
        return y_out * 0.5

    @classmethod
    def _diff_xx(cls, img):
        """ X-X Difference """
        x_left = img[:, :, 1:2, :] + img[:, :, 0:1, :]
        x_inner = img[:, :, 2:, :] + img[:, :, :-2, :]
        x_right = img[:, :, -1:, :] + img[:, :, -2:-1, :]
        x_out = K.concatenate([x_left, x_inner, x_right], axis=2)
        return x_out - 2.0 * img

    @classmethod
    def _diff_yy(cls, img):
        """ Y-Y Difference """
        y_top = img[:, 1:2, :, :] + img[:, 0:1, :, :]
        y_inner = img[:, 2:, :, :] + img[:, :-2, :, :]
        y_bot = img[:, -1:, :, :] + img[:, -2:-1, :, :]
        y_out = K.concatenate([y_top, y_inner, y_bot], axis=1)
        return y_out - 2.0 * img

    @classmethod
    def _diff_xy(cls, img):
        """ X-Y Difference """
        # xout1
        top_left = img[:, 1:2, 1:2, :] + img[:, 0:1, 0:1, :]
        inner_left = img[:, 2:, 1:2, :] + img[:, :-2, 0:1, :]
        bot_left = img[:, -1:, 1:2, :] + img[:, -2:-1, 0:1, :]
        xy_left = K.concatenate([top_left, inner_left, bot_left], axis=1)

        top_mid = img[:, 1:2, 2:, :] + img[:, 0:1, :-2, :]
        mid_mid = img[:, 2:, 2:, :] + img[:, :-2, :-2, :]
        bot_mid = img[:, -1:, 2:, :] + img[:, -2:-1, :-2, :]
        xy_mid = K.concatenate([top_mid, mid_mid, bot_mid], axis=1)

        top_right = img[:, 1:2, -1:, :] + img[:, 0:1, -2:-1, :]
        inner_right = img[:, 2:, -1:, :] + img[:, :-2, -2:-1, :]
        bot_right = img[:, -1:, -1:, :] + img[:, -2:-1, -2:-1, :]
        xy_right = K.concatenate([top_right, inner_right, bot_right], axis=1)

        # Xout2
        top_left = img[:, 0:1, 1:2, :] + img[:, 1:2, 0:1, :]
        inner_left = img[:, :-2, 1:2, :] + img[:, 2:, 0:1, :]
        bot_left = img[:, -2:-1, 1:2, :] + img[:, -1:, 0:1, :]
        xy_left = K.concatenate([top_left, inner_left, bot_left], axis=1)

        top_mid = img[:, 0:1, 2:, :] + img[:, 1:2, :-2, :]
        mid_mid = img[:, :-2, 2:, :] + img[:, 2:, :-2, :]
        bot_mid = img[:, -2:-1, 2:, :] + img[:, -1:, :-2, :]
        xy_mid = K.concatenate([top_mid, mid_mid, bot_mid], axis=1)

        top_right = img[:, 0:1, -1:, :] + img[:, 1:2, -2:-1, :]
        inner_right = img[:, :-2, -1:, :] + img[:, 2:, -2:-1, :]
        bot_right = img[:, -2:-1, -1:, :] + img[:, -1:, -2:-1, :]
        xy_right = K.concatenate([top_right, inner_right, bot_right], axis=1)

        xy_out1 = K.concatenate([xy_left, xy_mid, xy_right], axis=2)
        xy_out2 = K.concatenate([xy_left, xy_mid, xy_right], axis=2)
        return (xy_out1 - xy_out2) * 0.25


class GMSDLoss(tf.keras.losses.Loss):  # pylint:disable=too-few-public-methods
    """ Gradient Magnitude Similarity Deviation Loss.

    Improved image quality metric over MS-SSIM with easier calculations

    References
    ----------
    http://www4.comp.polyu.edu.hk/~cslzhang/IQA/GMSD/GMSD.htm
    https://arxiv.org/ftp/arxiv/papers/1308/1308.3052.pdf
    """
    def __init__(self):
        super().__init__(name="gmsd_loss", reduction=tf.keras.losses.Reduction.NONE)

    def call(self, y_true, y_pred):
        """ Return the Gradient Magnitude Similarity Deviation Loss.


        Parameters
        ----------
        y_true: tensor or variable
            The ground truth value
        y_pred: tensor or variable
            The predicted value

        Returns
        -------
        tensor
            The loss value
        """
        true_edge = self._scharr_edges(y_true, True)
        pred_edge = self._scharr_edges(y_pred, True)
        ephsilon = 0.0025
        upper = 2.0 * true_edge * pred_edge
        lower = K.square(true_edge) + K.square(pred_edge)
        gms = (upper + ephsilon) / (lower + ephsilon)
        gmsd = K.std(gms, axis=(1, 2, 3), keepdims=True)
        gmsd = K.squeeze(gmsd, axis=-1)
        return gmsd

    @classmethod
    def _scharr_edges(cls, image, magnitude):
        """ Returns a tensor holding modified Scharr edge maps.

        Parameters
        ----------
        image: tensor
            Image tensor with shape [batch_size, h, w, d] and type float32. The image(s) must be
            2x2 or larger.
        magnitude: bool
            Boolean to determine if the edge magnitude or edge direction is returned

        Returns
        -------
        tensor
            Tensor holding edge maps for each channel. Returns a tensor with shape `[batch_size, h,
            w, d, 2]` where the last two dimensions hold `[[dy[0], dx[0]], [dy[1], dx[1]], ...,
            [dy[d-1], dx[d-1]]]` calculated using the Scharr filter.
        """

        # Define vertical and horizontal Scharr filters.
        static_image_shape = image.get_shape()
        image_shape = K.shape(image)

        # 5x5 modified Scharr kernel ( reshape to (5,5,1,2) )
        matrix = np.array([[[[0.00070, 0.00070]],
                            [[0.00520, 0.00370]],
                            [[0.03700, 0.00000]],
                            [[0.00520, -0.0037]],
                            [[0.00070, -0.0007]]],
                           [[[0.00370, 0.00520]],
                            [[0.11870, 0.11870]],
                            [[0.25890, 0.00000]],
                            [[0.11870, -0.1187]],
                            [[0.00370, -0.0052]]],
                           [[[0.00000, 0.03700]],
                            [[0.00000, 0.25890]],
                            [[0.00000, 0.00000]],
                            [[0.00000, -0.2589]],
                            [[0.00000, -0.0370]]],
                           [[[-0.0037, 0.00520]],
                            [[-0.1187, 0.11870]],
                            [[-0.2589, 0.00000]],
                            [[-0.1187, -0.1187]],
                            [[-0.0037, -0.0052]]],
                           [[[-0.0007, 0.00070]],
                            [[-0.0052, 0.00370]],
                            [[-0.0370, 0.00000]],
                            [[-0.0052, -0.0037]],
                            [[-0.0007, -0.0007]]]])
        num_kernels = [2]
        kernels = K.constant(matrix, dtype='float32')
        kernels = K.tile(kernels, [1, 1, image_shape[-1], 1])

        # Use depth-wise convolution to calculate edge maps per channel.
        # Output tensor has shape [batch_size, h, w, d * num_kernels].
        pad_sizes = [[0, 0], [2, 2], [2, 2], [0, 0]]
        padded = tf.pad(image,  # pylint:disable=unexpected-keyword-arg,no-value-for-parameter
                        pad_sizes,
                        mode='REFLECT')
        output = K.depthwise_conv2d(padded, kernels)

        if not magnitude:  # direction of edges
            # Reshape to [batch_size, h, w, d, num_kernels].
            shape = K.concatenate([image_shape, num_kernels], axis=0)
            output = K.reshape(output, shape=shape)
            output.set_shape(static_image_shape.concatenate(num_kernels))
            output = tf.atan(K.squeeze(output[:, :, :, :, 0] / output[:, :, :, :, 1], axis=None))
        # magnitude of edges -- unified x & y edges don't work well with Neural Networks
        return output


class LossWrapper():
    """ A wrapper class for multiple keras losses to enable multiple masked weighted loss
    functions on a single output.

    Notes
    -----
    Whilst Keras does allow for applying multiple weighted loss functions, it does not allow
    for an easy mechanism to add additional data (in our case masks) that are batch specific
    but are not fed in to the model.

    This wrapper receives this additional mask data for the batch stacked onto the end of the
    color channels of the received :param:`y_true` batch of images. These masks are then split
    off the batch of images and applied to both the :param:`y_true` and :param:`y_pred` tensors
    prior to feeding into the loss functions.

    For example, for an image of shape (4, 128, 128, 3) 3 additional masks may be stacked onto
    the end of y_true, meaning we receive an input of shape (4, 128, 128, 6). This wrapper then
    splits off (4, 128, 128, 3:6) from the end of the tensor, leaving the original y_true of
    shape (4, 128, 128, 3) ready for masking and feeding through the loss functions.
    """
    def __init__(self) -> None:
        logger.debug("Initializing: %s", self.__class__.__name__)
        self._loss_functions = []
        self._loss_weights = []
        self._mask_channels = []
        logger.debug("Initialized: %s", self.__class__.__name__)

    def add_loss(self,
                 function: tf.keras.losses.Loss,
                 weight: float = 1.0,
                 mask_channel: int = -1) -> None:
        """ Add the given loss function with the given weight to the loss function chain.

        Parameters
        ----------
        function: :class:`tf.keras.losses.Loss`
            The loss function to add to the loss chain
        weight: float, optional
            The weighting to apply to the loss function. Default: `1.0`
        mask_channel: int, optional
            The channel in the `y_true` image that the mask exists in. Set to `-1` if there is no
            mask for the given loss function. Default: `-1`
        """
        logger.debug("Adding loss: (function: %s, weight: %s, mask_channel: %s)",
                     function, weight, mask_channel)
        # Loss must be compiled inside LossContainer for keras to handle distibuted strategies
        self._loss_functions.append(compile_utils.LossesContainer(function))
        self._loss_weights.append(weight)
        self._mask_channels.append(mask_channel)

    def __call__(self, y_true: tf.Tensor, y_pred: tf.Tensor) -> tf.Tensor:
        """ Call the sub loss functions for the loss wrapper.

        Loss is returned as the weighted sum of the chosen losses.

        If masks are being applied to the loss function inputs, then they should be included as
        additional channels at the end of :param:`y_true`, so that they can be split off and
        applied to the actual inputs to the selected loss function(s).

        Parameters
        ----------
        y_true: :class:`tensorflow.Tensor`
            The ground truth batch of images, with any required masks stacked on the end
        y_pred: :class:`tensorflow.Tensor`
            The batch of model predictions

        Returns
        -------
        :class:`tensorflow.Tensor`
            The final weighted loss
        """
        loss = 0.0
        for func, weight, mask_channel in zip(self._loss_functions,
                                              self._loss_weights,
                                              self._mask_channels):
            logger.debug("Processing loss function: (func: %s, weight: %s, mask_channel: %s)",
                         func, weight, mask_channel)
            n_true, n_pred = self._apply_mask(y_true, y_pred, mask_channel)
            loss += (func(n_true, n_pred) * weight)
        return loss

    @classmethod
    def _apply_mask(cls,
                    y_true: tf.Tensor,
                    y_pred: tf.Tensor,
                    mask_channel: int,
                    mask_prop: float = 1.0) -> Tuple[tf.Tensor, tf.Tensor]:
        """ Apply the mask to the input y_true and y_pred. If a mask is not required then
        return the unmasked inputs.

        Parameters
        ----------
        y_true: tensor or variable
            The ground truth value
        y_pred: tensor or variable
            The predicted value
        mask_channel: int
            The channel within y_true that the required mask resides in
        mask_prop: float, optional
            The amount of mask propagation. Default: `1.0`

        Returns
        -------
        tf.Tensor
            The ground truth batch of images, with the required mask applied
        tf.Tensor
            The predicted batch of images with the required mask applied
        """
        if mask_channel == -1:
            logger.debug("No mask to apply")
            return y_true[..., :3], y_pred[..., :3]

        logger.debug("Applying mask from channel %s", mask_channel)
        mask = K.expand_dims(y_true[..., mask_channel], axis=-1)
        mask_as_k_inv_prop = 1 - mask_prop
        mask = (mask * mask_prop) + mask_as_k_inv_prop

        n_true = K.concatenate([y_true[..., i:i + 1] * mask for i in range(3)], axis=-1)
        n_pred = K.concatenate([y_pred[..., i:i + 1] * mask for i in range(3)], axis=-1)

        return n_true, n_pred
