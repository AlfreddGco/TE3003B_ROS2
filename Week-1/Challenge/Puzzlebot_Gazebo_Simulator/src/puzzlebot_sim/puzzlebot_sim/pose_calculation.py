import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

import numpy as np
from time import time
from tf2_ros import TransformBroadcaster

from geometry_msgs.msg import Twist, TransformStamped, Vector3
from tf2_geometry_msgs import PoseStamped

TOPIC_VEL_CMD = '/cmd_vel'
TOPIC_CALCULATED_POSE = '/calculated_pose'

def quaternion_from_euler(roll, pitch, yaw):
  qx = np.sin(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) - np.cos(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
  qy = np.cos(roll/2) * np.sin(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.cos(pitch/2) * np.sin(yaw/2)
  qz = np.cos(roll/2) * np.cos(pitch/2) * np.sin(yaw/2) - np.sin(roll/2) * np.sin(pitch/2) * np.cos(yaw/2)
  qw = np.cos(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
  return [qx, qy, qz, qw]


class PoseCalculation(Node):
    def __init__(self):
        super().__init__('puzzlebot_pose_calculation')
        self.create_subscription(Twist, TOPIC_VEL_CMD,
            self.calculate_position, 10)
        self.publisher_pose = self.create_publisher(
            PoseStamped, TOPIC_CALCULATED_POSE, 10) 
        
        self.broadcaster = TransformBroadcaster(self)

        self.x, self.y, self.theta = 0, 0, 0
        self.t = 0


    def calculate_position(self, twist_vel):
        linear_vel = twist_vel.linear.x
        angular_vel = twist_vel.angular.z
        now = time()
        dt = now - self.t
        self.theta = angular_vel*dt
        self.x += linear_vel*dt * np.cos(self.theta)
        self.y += linear_vel*dt * np.sin(self.theta)
        self.t = now
        self.publish_pose_and_transform()


    def publish_pose_and_transform(self):
        stamped_pose = PoseStamped()
        stamped_pose.header.frame_id = 'base_link'

        stamped_pose.pose.position.x = self.x
        stamped_pose.pose.position.y = self.y

        # TODO: Do direct calculation only with yaw
        q = quaternion_from_euler(0, 0, self.theta)
        stamped_pose.pose.orientation.x = q[0]
        stamped_pose.pose.orientation.y = q[1]
        stamped_pose.pose.orientation.z = q[2]
        stamped_pose.pose.orientation.w = q[3]
        self.publisher_pose.publish(stamped_pose)

        stamped_transform = TransformStamped()
        stamped_transform.header.stamp = self.get_clock().now().to_msg()
        stamped_transform.header.frame_id = 'base_link'
        stamped_transform.child_frame_id = 'chassis'
        stamped_transform.transform.translation.x = self.x
        stamped_transform.transform.translation.y = self.y
        stamped_transform.transform.rotation = stamped_pose.pose.orientation
        self.broadcaster.sendTransform(stamped_transform)


if __name__ == '__main__':
    rclpy.init()
    node = PoseCalculation()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
