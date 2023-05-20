#!/usr/bin/env python3
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

import numpy as np
import math
from std_msgs.msg import Float32
from geometry_msgs.msg import Point
from nav_msgs.msg import Odometry
from tf_transformations import quaternion_from_euler 

class Localisation(Node):
    def __init__(self):
        super().__init__('puzzlebot_localisation')
        self.get_logger().info('init...')
        self.time_now = self.get_clock().now()
        self.rate = self.create_rate(60)
        self.wl, self.wr = 0.0 , 0.0
        self.kr, self.kl = 100.0, 100.0
        self.wheel_radius = 0.05
        self.wheel_distance = 0.08
        self.pose = np.array([0, 0, 0], dtype=np.float64)
        self.create_subscription(Float32, '/wl', self.update_wl, 10)
        self.create_subscription(Float32, '/wr', self.update_wr, 10)
        self.odom = self.create_publisher(Odometry, '/odom', 10)
        # Define covariance matrix
        self.covariance_matrix = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                  0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                  0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                  0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                  0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                  0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        
        self.odomConstants = self.fill_odomerty()
        self.Qk = np.array([
            [0.5, 0.01, 0.01],
            [0.01, 0.5, 0.01],
            [0.01, 0.01, 0.2]
        ] )
        self.Hk = np.identity(3)
        self.sigmak = np.zeros(3)
    
    def update_wl(self, wl: Float32):
        self.wl = wl.data
        self.get_logger().info("{} left wheel".format(self.wl))

    def update_wr(self, wr: Float32):
        self.wr = wr.data
        self.get_logger().info("{} right wheel".format(self.wr))

    def calculate_odometry(self):
        self.get_logger().info('calculating odometry...')
        l = self.wheel_distance
        mat = np.array([[.5, .5], [1/l, -1/l]])
        deltaD, deltaTheta = np.dot(mat, np.array([self.wr, self.wl])*self.wheel_radius)
        self.calculcate_covariance(deltaD)
        self.pose += np.array([deltaD * math.cos(self.pose[2]), deltaD * math.sin(self.pose[2]), deltaTheta])/self.rate

        self.odomConstants.pose.pose.position = Point(self.pose[0], self.pose[1], self.wheel_radius)
        q = quaternion_from_euler(0, 0, self.pose[2])
        self.odomConstants.header.stamp = self.time_now.to_msg()
        self.odomConstants.pose.pose.orientation.x = q[0]
        self.odomConstants.pose.pose.orientation.y = q[1]
        self.odomConstants.pose.pose.orientation.z = q[2]
        self.odomConstants.pose.pose.orientation.w = q[3]
        self.odomConstants.twist.twist.linear.x = deltaD
        self.odomConstants.twist.twist.angular.z = deltaTheta
        self.odom.publish(self.odomConstants)

    def calculcate_covariance(self, deltaD):
        self.get_logger().info('calculating covariance...')
        self.Hk[0][2] = -deltaD * math.sin(self.pose[2])/self.rate
        self.Hk[1][2] = deltaD * math.cos(self.pose[2])/self.rate
        wk = self.wheel_radius/(2*self.rate)*np.array([[math.cos(self.pose[2]),math.cos(self.pose[2])],
                                           [math.sin(self.pose[2]),math.sin(self.pose[2])],
                                           [2/self.wheel_distance, -2/self.wheel_distance]])
        Edk = np.array([[self.kr*abs(self.wr), 0],
                       [0, self.kl*abs(self.wl)]])
      
        self.Qk = np.dot(np.dot(wk,Edk),np.transpose(wk))
        self.sigmak = np.dot(np.dot(self.Hk, self.sigmak), np.transpose(self.Hk))+self.Qk
        self.odomConstants.pose.covariance[0] = self.sigmak[0][0] 
        self.odomConstants.pose.covariance[1] = self.sigmak[0][1]
        self.odomConstants.pose.covariance[5] = self.sigmak[0][2]
        self.odomConstants.pose.covariance[6] = self.sigmak[1][0]
        self.odomConstants.pose.covariance[7] = self.sigmak[1][1]
        self.odomConstants.pose.covariance[11] = self.sigmak[1][2]
        self.odomConstants.pose.covariance[30] = self.sigmak[2][0]
        self.odomConstants.pose.covariance[31] = self.sigmak[2][1]
        self.odomConstants.pose.covariance[35] = self.sigmak[2][2]
        
    def fill_odomerty(self)-> Odometry:
        self.get_logger().info('getting odometry msgs...')
        self.get_logger().info("{} time now".format(self.get_clock().now().to_msg()._sec), once=True)
        odometry = Odometry()
        odometry.header.stamp = self.time_now.to_msg()
        odometry.header.frame_id = 'base_link'
        odometry.child_frame_id = 'chassis'
        odometry.pose.pose.position.x = 0.0
        odometry.pose.pose.position.y = 0.0
        odometry.pose.pose.position.z = (self.wheel_radius)
        odometry.pose.pose.orientation.x = 0.0
        odometry.pose.pose.orientation.y = 0.0
        odometry.pose.pose.orientation.z = 0.0
        odometry.pose.pose.orientation.w = 0.0
        # self.get_logger().info("{} odometry pose w".format(odometry.pose.pose.orientation.w), once=True)
        odometry.pose.covariance = self.covariance_matrix
        
        odometry.twist.twist.linear.x = 0.0
        odometry.twist.twist.linear.y = 0.0
        odometry.twist.twist.linear.z = 0.0
        odometry.twist.twist.angular.x = 0.0
        odometry.twist.twist.angular.y = 0.0
        odometry.twist.twist.angular.z = 0.0
        self.get_logger().info("{} odometry twist z".format(odometry.twist.twist.angular.z), once=True)
        odometry.twist.covariance = self.covariance_matrix
        self.get_logger().info("{} odometry twist covariance".format(odometry.twist.covariance), once=True)
        return odometry
    
    def run(self):
        self.get_logger().info("run ...")     
        self.calculate_odometry()
        # Sleep to maintain the loop rate
        self.rate.sleep()

def main():
    rclpy.init()
    executor = MultiThreadedExecutor()
    node = Localisation()
    executor.add_node(node)
    task = executor.create_task(node.run)
    try:
        executor.spin_until_future_complete(task)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

if (__name__== '__main__') :
    main()
    