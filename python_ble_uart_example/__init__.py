import sys
import asyncio
import argparse
import time

from bleak import BleakClient, discover
from bleak.uuids import uuid16_dict


class BLEUARTConnection:
    def __init__(self, client, rx, tx):
        self.client = client
        self.rx_char = rx
        self.tx_char = tx

        self.buffer = ''

    async def start(self):
        await self.client.start_notify(self.tx_char, self.rx_callback)

    def rx_callback(self, sender: int, data: bytearray):
        self.buffer += data.decode('utf8')

        if '\n' in self.buffer:
            lines = self.buffer.split('\n')
            for line in lines[:-1]:
                print(line)
            self.buffer = lines[-1]

    async def send(self, message):
        await self.client.write_gatt_char(self.rx_char, bytearray(message.encode('utf8')))


def get_uart_characteristics(client):
    # Find the Nordic UART service based on its description
    uart_service = None
    for service in client.services:
        if service.description == 'Nordic UART Service':
            uart_service = service
            break
    
    if uart_service is None:
        raise Exception('Failed to find UART service')

    rx = None
    tx = None
    for characteristic in uart_service.characteristics:
        if characteristic.description == 'TXD':
            tx = characteristic

        if 'write' in characteristic.properties:
            rx = characteristic

        if rx is not None and tx is not None:
            break

    return (rx, tx)


async def rxtx(address_or_device):
    async with BleakClient(address_or_device) as client:
        await client.is_connected()

        rx, tx = get_uart_characteristics(client)

        uart_connection = BLEUARTConnection(client, rx, tx)
        await uart_connection.start()

        while True:
            await uart_connection.send('hello from pc\r\n')
            await asyncio.sleep(1)


async def scan():
    for device in await discover():
        print(f'{device.address}\t{device.name}')


async def discover_device_by_name(name):
    for device in await discover():
        if device.name == name:
            return device

    return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Send and receive Nordic BLE UART data')
    parser.add_argument('--address')
    parser.add_argument('--name')
    parser.add_argument('--scan', default=False, action='store_true')

    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    if args.address and args.name:
        print('Specify either name or address but not both')
        sys.exit(1)

    if args.scan:
        loop.run_until_complete(scan())
    else:
        if args.address:
            target = args.address
        elif args.name:
            device = loop.run_until_complete(discover_device_by_name(args.name))

            if device == None:
                print('Scan failed to find device with specified name')
                sys.exit(1)

            target = device

        loop.run_until_complete(rxtx(target))

