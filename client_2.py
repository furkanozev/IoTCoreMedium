# Copyright 2022 Massimiliano Angelino
# SPDX-License-Identifier: MIT-0

from __future__ import absolute_import
from __future__ import print_function
import argparse
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import sys
import threading
import time
from uuid import uuid4

# This sample uses the Message Broker for AWS IoT to send and receive messages
# through an MQTT connection. On startup, the device connects to the server,
# subscribes to a topic, and begins publishing messages to that topic.
# The device should receive those same messages back from the message broker,
# since it is subscribed to that same topic.


endpoint = "<endpoint>"
root_ca = "./RootCA.pem"
id = "furkantest"
token_name = "token"
signature = "testSignature"
authorizer_name = "IoTCoreAuthorizer"
token = "testToken"
topic = "mqtt-dev/device/furkantest/1/send"
topic2 = "mqtt-dev/device/furkantest/1/receive"
message = "testMessage"
count = 0


received_count = 0
received_all_event = threading.Event()

# Callback when connection is accidentally lost.


def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(
        return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)


def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    print("Resubscribe results: {}".format(resubscribe_results))

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))


# Callback when the subscribed topic receives a message
def on_message_received(topic, payload, **kwargs):
    print("Received message from topic '{}': {}".format(topic, payload))
    global received_count
    received_count += 1
    if received_count == count:
        received_all_event.set()

def add_headers(transform_args):
    transform_args.http_request.headers.add(
        'x-amz-customauthorizer-name', authorizer_name)
    transform_args.http_request.headers.add(
        'x-amz-customauthorizer-signature', signature)
    transform_args.http_request.headers.add(token_name, token)

    transform_args.set_done()

if __name__ == '__main__':
    # Spin up resources
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    tls_options = io.TlsContextOptions()

    socket_options = io.SocketOptions()

    if root_ca: 
        tls_options.override_default_trust_store_from_path(ca_dirpath=None,
            ca_filepath=root_ca)
    tls_ctx = io.ClientTlsContext(options=tls_options)

    client = mqtt.Client(client_bootstrap, tls_ctx)

    mqtt_connection = mqtt.Connection(client=client,
        host_name=endpoint,
        port=443,
        on_connection_interrupted=on_connection_interrupted,
        on_connection_resumed=on_connection_resumed,
        client_id=id,
        clean_session=True,
        keep_alive_secs=60,
        socket_options=socket_options,
        use_websockets=True,
        websocket_handshake_transform=add_headers
        )

    print("Connecting to {} with client ID '{}'...".format(
        endpoint, id))

    connect_future = mqtt_connection.connect()

    # Future.result() waits until a result is available
    connect_future.result()
    print("Connected!")

    # Subscribe
    print("Subscribing to topic '{}'...".format(topic))
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic=topic2,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received)

    subscribe_result = subscribe_future.result()
    print("Subscribed with {}".format(str(subscribe_result['qos'])))

    # Publish message to server desired number of times.
    # This step is skipped if message is blank.
    # This step loops forever if count was set to 0.
    if message:
        if count == 0:
            print("Sending messages until program killed")
        else:
            print("Sending {} message(s)".format(count))

        publish_count = 1
        while (publish_count <= count) or (count == 0):
            message = "{} [{}]".format(message, publish_count)
            print("Publishing message to topic '{}': {}".format(
                topic, message))
            mqtt_connection.publish(
                topic=topic,
                payload=message,
                qos=mqtt.QoS.AT_LEAST_ONCE)
            time.sleep(1)
            publish_count += 1

    # Wait for all messages to be received.
    # This waits forever if count was set to 0.
    if count != 0 and not received_all_event.is_set():
        print("Waiting for all messages to be received...")

    received_all_event.wait()
    print("{} message(s) received.".format(received_count))

    # Disconnect
    print("Disconnecting...")
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
    print("Disconnected!")