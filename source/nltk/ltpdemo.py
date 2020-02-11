import sys
import os
from pyltp import Segmentor
from macpath import join


if __name__=="__main__":
    model_path = "C:\\Users\\ThinkPad\\Desktop\\cws.model"
    segmentor = Segmentor()
    segmentor.load(model_path)
    
    words = segmentor.segment("�ڰ�����������н�ռ�����")
    print ("|".join(words))
    