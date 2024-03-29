import os
import sys
import numpy as np
import time
import cv2
from os import listdir
from os.path import isfile, join, isdir
import random
from sklearn.tree import DecisionTreeClassifier
from UCSDped1 import TestVideoFile
from sklearn.neighbors import KNeighborsClassifier
from model import VideoClassifier
import time
from sklearn.metrics import roc_curve, auc
from scipy.interpolate import interp1d
from scipy.optimize import brentq


def draw_str(dst, target, s):
    x, y = target
    cv2.putText(dst, s, (x+1, y+1), cv2.FONT_HERSHEY_PLAIN, 1.0,
                (0, 0, 0), thickness=2, lineType=cv2.LINE_AA)
    cv2.putText(dst, s, (x, y), cv2.FONT_HERSHEY_PLAIN,
                1.0, (255, 255, 255), lineType=cv2.LINE_AA)


def passed_time(previous_time):
    return round(time.time() - previous_time, 3)


FEATURES_PATH = os.path.join(
    r'Anomaly_Detection-master\anomaly-detection-master', 'features')


def load_train_features(feature_type, features_path=FEATURES_PATH):

    print(f"Loading features from: {features_path}")

    try:
        features = [f for f in os.listdir(features_path) if f.startswith(
            f"features_test_{feature_type}")]
    except FileNotFoundError as e:
        print(f"Error loading features: {e}")
        raise

    x_train = []
    y_train = []

    for feature in features:
        with open(os.path.join(features_path, feature), 'r') as file:
            for line in file:
                if line.strip():
                    data = [float(x) for x in line.split()]
                    x_train.append(data[:-1])
                    y_train.append(int(data[-1]))

    return x_train, np.array(y_train)


if __name__ == '__main__':

    feature_type = 'ped1'

    x_train, y_train = load_train_features(feature_type)

    # remaining code to train model, test, etc...


def compute_roc_EER(fpr, tpr):
    roc_EER = []
    cords = zip(fpr, tpr)
    for item in cords:
        item_fpr, item_tpr = item
        if item_tpr + item_fpr == 1.0:
            roc_EER.append((item_fpr, item_tpr))
    assert (len(roc_EER) == 1.0)
    return np.array(roc_EER)


class UCSDTest:
    def __init__(self, path, n, detect_interval, type):
        self.path = path
        self.fgbg = cv2.createBackgroundSubtractorMOG2()
        self.n = n
        self.detect_interval = detect_interval
        # self.classifier = VideoClassifier()
        self.clf = DecisionTreeClassifier(max_depth=5)
        x, y = load_train_features(type)
        self.clf.fit(x, y)
        self.true_positive = 0.0
        self.false_positive = 0.0
        self.false_negative = 0.0
        self.should_find = 0.0
        self.total = 0.0
        self.y = []
        self.y_pred = []

    def process_frame(self, bins, magnitude, fmask, tag_img, frame):
        if np.count_nonzero(fmask) == 0:
            return False
        bin_count = np.zeros(9, np.uint8)
        h, w = bins.shape
        found_anomaly = False
        features_j = []
        tag_j = []
        index_i_j = []
        for i in range(0, h, self.n):
            i_end = min(h, i+self.n)
            if np.count_nonzero(fmask[i]) > 0:
                for j in range(0, w, self.n):
                    j_end = min(w, j+self.n)
                    if np.count_nonzero(fmask[i:i_end, j:j_end]) > 0:
                        # Get the atom for bins
                        atom_bins = bins[i:i_end, j:j_end].flatten()

                        # Average magnitude
                        atom_mag = magnitude[i:i_end, j:j_end].flatten().mean()
                        atom_fmask = fmask[i:i_end, j:j_end].flatten()

                        # Count of foreground values
                        f_cnt = np.count_nonzero(atom_fmask)
                        f_cnt_2 = np.count_nonzero(
                            fmask[i:i_end, j:j_end].flatten())

                        # Get the direction bins values
                        hs, _ = np.histogram(atom_bins, np.arange(10))
                        features = hs.tolist()
                        features.extend(
                            [f_cnt, f_cnt_2, atom_mag, i, i+self.n, j, j+self.n])
                        features_j.append(features)
                        # vector = np.array(features)
                        tag_atom = tag_img[i:i_end, j:j_end].flatten()
                        ones = np.count_nonzero(tag_atom)
                        # if ones > 20:
                        #     tag = 1
                        # else:
                        #     tag = 0
                        tag = 1
                        if ones < 50:
                            tag = 0
                        tag_j.append(tag)
                        index_i_j.append((i, j))
        predicted = self.clf.predict(features_j, tag_j)
        self.y_pred.extend(predicted)
        self.y.extend(tag_j)
        self.total += len(predicted)
        # predicted = self.classifier.predict(features_j, tag_j)
        # self.true_positive += true_positive
        for index, pred in enumerate(predicted):
            pred = pred.item()
            i, j = index_i_j[index]
            if pred == 1:
                if tag_j[index] == 0:
                    self.false_positive += 1
                else:
                    self.true_positive += 1
                j_end = min(w, j+self.n)
                i_end = min(h, i+self.n)
                cv2.rectangle(frame, (j, i), (j_end, i_end), (255, 0, 0), 2)
                found_anomaly = True
            elif tag_j[index] == 1:
                self.false_negative += 1
                # if tag == 1:
                #     self.should_find += 1
                # if predicted == tag and predicted == 1:
                #     self.correct += 1
                # if predicted == 1:
                #     self.found += 1
        return found_anomaly

    def process_video(self, video_name, tag_video):
        mag_threshold = 1e-3
        elements = 0
        files = [f for f in listdir(
            self.path+video_name) if isfile(join(self.path+video_name, f))]
        if '.DS_Store' in files:
            files.remove('.DS_Store')
        if '._.DS_Store' in files:
            files.remove('._.DS_Store')
        files_tag = [f for f in listdir(
            self.path+tag_video) if isfile(join(self.path+tag_video, f))]
        if '.DS_Store' in files_tag:
            files_tag.remove('.DS_Store')
        if '._.DS_Store' in files_tag:
            files_tag.remove('._.DS_Store')
        files_tag.sort()
        files.sort()
        number_frame = 0
        old_frame = None
        mots = []
        old_frame = cv2.imread(self.path + video_name +
                               '001.tif', cv2.IMREAD_GRAYSCALE)
        width = old_frame.shape[0]
        height = old_frame.shape[1]
        h, w = old_frame.shape[:2]
        bins = np.zeros((h, w, self.detect_interval), np.uint8)
        mag = np.zeros((h, w, self.detect_interval), np.float32)
        fmask = np.zeros((h, w, self.detect_interval), np.uint8)
        frames = np.zeros((h, w, self.detect_interval), np.uint8)
        tag_img = np.zeros((h, w, self.n), np.uint8)
        anomaly_detected = []
        for tif in files:
            movement = 0
            frame = cv2.imread(self.path + video_name +
                               tif, cv2.IMREAD_GRAYSCALE)
            if number_frame % self.detect_interval == 0:
                fmask = self.fgbg.apply(frame)
                flow = cv2.calcOpticalFlowFarneback(
                    old_frame, frame, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                tag_img = cv2.imread(
                    self.path + tag_video + files_tag[number_frame], cv2.IMREAD_GRAYSCALE)
                # Calculate direction and magnitude
                height, width = flow.shape[:2]
                fx, fy = flow[:, :, 0], flow[:, :, 1]
                angle = ((np.arctan2(fy, fx+1) + 2*np.pi)*180) % 360
                binno = np.ceil(angle/45)
                magnitude = np.sqrt(fx*fx+fy*fy)
                binno[magnitude < mag_threshold] = 0
                bins = binno
                mag = magnitude
                # if number_frame % self.detect_interval == 0:
                found_anomaly = self.process_frame(
                    bins, mag, fmask, tag_img, frame)
                if found_anomaly:
                    anomaly_detected.append(number_frame)
            cv2.imshow('frame', frame)
            number_frame += 1
            old_frame = frame
            k = cv2.waitKey(30) & 0xff
            if k == 27:
                break
        cv2.destroyAllWindows()
        return anomaly_detected


if __name__ == '__main__':
    ucsdped = 'UCSDped1'
    # Use your actual path
    dataset_path = (r"Anomaly_Detection-master\UCSD_Anomaly_Dataset.v1p2")

    ucsd_test = UCSDTest(os.path.join(
        dataset_path, ucsdped, "Test/"), 10, 5, ucsdped)
    dir_test = [f for f in os.listdir(os.path.join(dataset_path, ucsdped, "Test/"))
                if os.path.isdir(os.path.join(dataset_path, ucsdped, "Test/", f))]
    dir_test.sort()
    total_correct = 0.0
    total_should_found = 0.0
    total_found = 0.0
    # dir_test = [dir_test[0]]
    for directory in dir_test:
        if not directory.endswith("gt"):
            print(directory)
            start_time = time.time()
            anomaly_detected = ucsd_test.process_video(
                directory+'/', directory + '_gt/')
            time_video = passed_time(start_time)
            print(200.0/time_video, "frames per second")
            total_found += len(anomaly_detected)
            index_video = int(directory[-3:])
            total_correct += len(set(anomaly_detected)
                                 .intersection(TestVideoFile[index_video]))
            total_should_found += len(TestVideoFile[index_video])
    precision = total_correct/total_found
    recall = total_correct/total_should_found
    f1 = 2.0*precision*recall/(precision+recall)
    print("Results frame wise:")
    print("Precision: ", precision)
    print("Recall: ", recall)
    print("F1: ", f1)
    print("Results pixel wise:")
    pixel_true_positive = ucsd_test.true_positive
    pixel_false_positive = ucsd_test.false_positive
    pixel_false_negative = ucsd_test.false_negative
    pixel_total = ucsd_test.total
    fpr, tpr, threshold = roc_curve(ucsd_test.y, ucsd_test.y_pred, pos_label=1)
    fnr = 1 - tpr
    eer = brentq(lambda x: 1. - x - interp1d(fpr, tpr)(x), 0., 1.)
    print("EER by pixel")
    print(eer)
    print("RD by pixel")
    print(1-eer)
    print("True positive: ", pixel_true_positive)
    print("False positive: ", pixel_false_positive)
    precision = pixel_true_positive / \
        (pixel_true_positive + pixel_false_positive)
    recall = pixel_true_positive/(pixel_true_positive + pixel_false_negative)
    f1 = 2.0*precision*recall/(precision+recall)
    print("Precision: ", precision)
    print("Recall: ", recall)
    print("F1: ", f1)
