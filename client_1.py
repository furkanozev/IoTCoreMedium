# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0.

from awsiot import mqtt5_client_builder
from awscrt import mqtt5
from concurrent.futures import Future
from time import time

TIMEOUT = 100

# cmdData is the arguments/input from the command line placed into a single struct for
# use in this sample. This handles all of the command line parsing, validating, etc.
# See the Utils/CommandLineUtils for more information.

future_stopped = Future()
future_connection_success = Future()

# Callback for the lifecycle event Stopped
def on_lifecycle_stopped(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    print("Lifecycle Stopped")
    global future_stopped
    future_stopped.set_result(lifecycle_stopped_data)


# Callback for the lifecycle event Connection Success
def on_lifecycle_connection_success(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    print("Lifecycle Connection Success")
    global future_connection_success
    future_connection_success.set_result(lifecycle_connect_success_data)
    
# Callback when any publish is received
def on_publish_received(publish_packet_data):
    publish_packet = publish_packet_data.publish_packet
    assert isinstance(publish_packet, mqtt5.PublishPacket)
    print(f"\tPublish received message on topic: {publish_packet.topic}")
    print(f"\tMessage: {publish_packet.payload}")

    if (publish_packet.user_properties is not None):
        if (publish_packet.user_properties.count > 0):
            for i in range(0, publish_packet.user_properties.count):
                user_property = publish_packet.user_properties[i]
                print(f"\t\twith UserProperty ({user_property.name}, {user_property.value})")


if __name__ == '__main__':


    client = mqtt5_client_builder.websockets_with_custom_authorizer(
        endpoint="<endpoint>",
        auth_authorizer_name="IotCoreAuthorizer_dev",
        auth_token_key_name="x-customauthorizer-token",
        auth_token_value="testToken",
        on_lifecycle_stopped=on_lifecycle_stopped,
        on_lifecycle_connection_success=on_lifecycle_connection_success,
        on_publish_received=on_publish_received,
        client_id="furkantest2/1")


    client.start()
    future_connection_success.result(TIMEOUT)
    print("Client Connected")
    
    subscribe_packet = mqtt5.SubscribePacket(
            subscriptions=[mqtt5.Subscription(
                topic_filter="$share/twin/mqtt-dev/device/furkantest2/receive",
                qos=mqtt5.QoS.AT_LEAST_ONCE)]
        )

    subscribe_one_future = client.subscribe(subscribe_packet)
    suback_one = subscribe_one_future.result(60)

while True:
    time.sleep(1)